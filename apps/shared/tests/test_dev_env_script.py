from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_script() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "scripts" / "dev-env"
    loader = importlib.machinery.SourceFileLoader("dev_env_script", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def test_parse_command_accepts_documented_surface() -> None:
    script = _load_script()

    assert script.parse_command([]) == "up"
    assert script.parse_command(["up"]) == "up"
    assert script.parse_command(["down"]) == "down"
    assert script.parse_command(["--down"]) == "down"
    assert script.parse_command(["reset"]) == "reset"
    assert script.parse_command(["--reset"]) == "reset"
    assert script.parse_command(["refresh-db"]) == "refresh-db"
    assert script.parse_command(["--refresh-db"]) == "refresh-db"
    assert script.parse_command(["refresh-assets"]) == "refresh-assets"
    assert script.parse_command(["--refresh-assets"]) == "refresh-assets"
    assert script.parse_command(["status"]) == "status"
    assert script.parse_command(["--status"]) == "status"
    assert script.parse_command(["--help"]) == "help"

    with pytest.raises(ValueError):
        script.parse_command(["up", "status"])
    with pytest.raises(ValueError):
        script.parse_command(["--unknown"])


def test_validate_dev_database_name_is_strict() -> None:
    script = _load_script()

    script.validate_dev_database_name("dirt_cloud_dev_0123abcdef")

    for name in [
        "dirt",
        "dirt_cloud_dev_prod",
        "dirt_cloud_dev_0123abcdeg",
        "dirt_cloud_dev_0123abcdef_extra",
    ]:
        with pytest.raises(ValueError):
            script.validate_dev_database_name(name)


def test_ensure_local_env_generates_local_only_values(tmp_path: Path) -> None:
    script = _load_script()
    paths = script.paths_for(tmp_path)
    paths.logs_dir.mkdir(parents=True)
    paths.dumps_dir.mkdir(parents=True)
    paths.assets_dir.mkdir(parents=True)
    runtime = script.Runtime(
        repo_root=tmp_path,
        worktree_id="0123abcdef" * 6 + "0123",
        web_port=5173,
        api_port=8023,
        database_name="dirt_cloud_dev_0123abcdef",
        api_url="http://127.0.0.1:8023",
        web_url="http://127.0.0.1:5173",
    )

    values = script.ensure_local_env(paths, runtime)
    reread = script.ensure_local_env(paths, runtime)

    assert values["DIRT_CLOUD_ADMIN_PASSWORD"] == reread["DIRT_CLOUD_ADMIN_PASSWORD"]
    assert values["DIRT_CLOUD_GATEWAY_TOKEN"] == reread["DIRT_CLOUD_GATEWAY_TOKEN"]
    assert values["DIRT_CLOUD_DATABASE_URL"].endswith("/dirt_cloud_dev_0123abcdef")
    assert values["DIRT_CLOUD_SESSION_COOKIE_SECURE"] == "false"
    assert values["DIRT_CLOUD_GATEWAY_COMMAND_CLAIM_ENABLED"] == "false"
    assert values["DIRT_CLOUD_ASSET_STORE"] == "local"
    assert values["DIRT_CLOUD_LOCAL_ASSET_ROOT"] == str(paths.assets_dir)
    assert "railway" not in paths.env_path.read_text().lower()
    assert stat.S_IMODE(paths.env_path.stat().st_mode) == 0o600


def test_ensure_local_env_repairs_empty_dev_pg_password_from_root_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _load_script()
    monkeypatch.delenv("DIRT_DEV_PG_PASSWORD", raising=False)
    monkeypatch.delenv("DIRT_PG_PASSWORD", raising=False)
    paths = script.paths_for(tmp_path)
    paths.logs_dir.mkdir(parents=True)
    paths.dumps_dir.mkdir(parents=True)
    paths.assets_dir.mkdir(parents=True)
    (tmp_path / ".env").write_text("DIRT_PG_PASSWORD=root-password\n")
    paths.env_path.parent.mkdir(parents=True, exist_ok=True)
    paths.env_path.write_text("DIRT_DEV_PG_PASSWORD=''\n")
    runtime = script.Runtime(
        repo_root=tmp_path,
        worktree_id="0123abcdef" * 6 + "0123",
        web_port=5173,
        api_port=8023,
        database_name="dirt_cloud_dev_0123abcdef",
        api_url="http://127.0.0.1:8023",
        web_url="http://127.0.0.1:5173",
    )

    values = script.ensure_local_env(paths, runtime)

    assert values["DIRT_DEV_PG_PASSWORD"] == "root-password"
    assert "DIRT_DEV_PG_PASSWORD=root-password" in paths.env_path.read_text()
    assert ":root-password@" in values["DIRT_CLOUD_DATABASE_URL"]


def test_build_child_env_strips_prod_and_keeps_local_values() -> None:
    script = _load_script()

    env = script.build_child_env(
        {
            "PATH": os.environ.get("PATH", ""),
            "DATABASE_URL": "postgresql://prod",
            "DATABASE_PUBLIC_URL": "postgresql://prod-public",
            "DIRT_CLOUD_API_BASE_URL": "https://prod.example",
            "DIRT_CLOUD_SESSION_SECRET": "prod-secret",
            "RAILWAY_PROJECT_ID": "prod-project",
        },
        {
            "DIRT_CLOUD_DATABASE_URL": "postgresql+asyncpg://dirt@127.0.0.1:5432/dirt_cloud_dev_0123abcdef",
            "DIRT_CLOUD_SESSION_SECRET": "local-secret",
        },
    )

    assert env["PATH"] == os.environ.get("PATH", "")
    assert env["DIRT_CLOUD_DATABASE_URL"].startswith("postgresql+asyncpg://dirt@")
    assert env["DIRT_CLOUD_SESSION_SECRET"] == "local-secret"
    assert env["PYTHONUNBUFFERED"] == "1"
    assert "DATABASE_URL" not in env
    assert "DATABASE_PUBLIC_URL" not in env
    assert "DIRT_CLOUD_API_BASE_URL" not in env
    assert "RAILWAY_PROJECT_ID" not in env


def test_process_commands_are_explicit() -> None:
    script = _load_script()

    assert script.api_command(8023) == [
        "uv",
        "run",
        "--package",
        "dirt-control-plane",
        "uvicorn",
        "dirt_control.app:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        "8023",
    ]
    assert script.web_command() == [
        "pnpm",
        "--dir",
        "web-ui",
        "dev",
        "--host",
        "127.0.0.1",
    ]


def test_pg_dump_command_uses_custom_format_without_url_or_password() -> None:
    script = _load_script()
    source = script.PgConnection(
        host="containers-us-west.example",
        port="6543",
        user="postgres",
        password="source-secret",
        database="railway",
        sslmode="require",
    )

    command = script.pg_dump_command(
        Path("var/dev/control-plane/dumps/demo.dump"), source
    )

    assert command[:2] == ["pg_dump", "-Fc"]
    assert "-f" in command
    assert "railway" in command
    assert "source-secret" not in command
    assert not any("postgresql://" in part for part in command)


def test_postgres_command_builders_honor_binary_overrides_without_secrets() -> None:
    script = _load_script()
    binaries = script.pg_binaries(
        {
            "DIRT_DEV_PG_DUMP_BIN": "/opt/pgsql-18/bin/pg_dump",
            "DIRT_DEV_PG_RESTORE_BIN": "/opt/pgsql-18/bin/pg_restore",
            "DIRT_DEV_DROPDB_BIN": "/opt/pgsql-18/bin/dropdb",
            "DIRT_DEV_CREATEDB_BIN": "/opt/pgsql-18/bin/createdb",
            "DIRT_DEV_PSQL_BIN": "/opt/pgsql-18/bin/psql",
        }
    )
    source = script.PgConnection(
        host="containers-us-west.example",
        port="6543",
        user="postgres",
        password="source-secret",
        database="railway",
        sslmode="require",
    )
    local = script.PgConnection(
        host="127.0.0.1",
        port="5432",
        user="dirt",
        password="local-secret",
        database="dirt_cloud_dev_0123abcdef",
    )

    commands = [
        script.pg_dump_command(Path("demo.dump"), source, binaries),
        script.dropdb_command(local, binaries),
        script.createdb_command(local, binaries),
        script.pg_restore_command(Path("demo.dump"), local, binaries),
        script.psql_command(local, binaries),
    ]

    assert [command[0] for command in commands] == [
        "/opt/pgsql-18/bin/pg_dump",
        "/opt/pgsql-18/bin/dropdb",
        "/opt/pgsql-18/bin/createdb",
        "/opt/pgsql-18/bin/pg_restore",
        "/opt/pgsql-18/bin/psql",
    ]
    flattened = [part for command in commands for part in command]
    assert "source-secret" not in flattened
    assert "local-secret" not in flattened
    assert not any("postgresql://" in part for part in flattened)


def test_pg_restore_command_ignores_original_ownership() -> None:
    script = _load_script()
    connection = script.PgConnection(
        host="127.0.0.1",
        port="5432",
        user="dirt",
        password="local-secret",
        database="dirt_cloud_dev_0123abcdef",
    )

    command = script.pg_restore_command(Path("demo.dump"), connection)

    assert "--no-owner" in command
    assert command.index("--no-owner") < command.index("-d")
    assert "local-secret" not in command
    assert not any("postgresql://" in part for part in command)


def test_pg_env_keeps_password_without_inheriting_cloud_secrets() -> None:
    script = _load_script()
    connection = script.PgConnection(
        host="127.0.0.1",
        port="5432",
        user="dirt",
        password="local-secret",
        database="dirt_cloud_dev_0123abcdef",
    )

    env = script.pg_env(
        {
            "PATH": "/usr/bin",
            "DIRT_CLOUD_SESSION_SECRET": "prod-secret",
            "RAILWAY_TOKEN": "railway-secret",
        },
        connection,
    )

    assert env["PATH"] == "/usr/bin"
    assert env["PGPASSWORD"] == "local-secret"
    assert "DIRT_CLOUD_SESSION_SECRET" not in env
    assert "RAILWAY_TOKEN" not in env


def test_database_mutation_commands_refuse_unsafe_names() -> None:
    script = _load_script()
    unsafe = script.PgConnection(
        host="127.0.0.1",
        port="5432",
        user="dirt",
        password="local-secret",
        database="dirt",
    )

    for builder in [
        script.dropdb_command,
        script.createdb_command,
        lambda connection: script.pg_restore_command(Path("demo.dump"), connection),
        script.psql_command,
    ]:
        with pytest.raises(ValueError):
            builder(unsafe)


def test_sanitization_sql_replaces_credentials_and_keeps_audit_rows() -> None:
    script = _load_script()

    sql = script.build_sanitization_sql(
        {
            "DIRT_CLOUD_GATEWAY_CREDENTIAL_ID": "dev-credential",
            "DIRT_CLOUD_GATEWAY_ID": "dev-gateway",
            "DIRT_CLOUD_GATEWAY_TOKEN_SHA256": "abc123",
            "DIRT_CLOUD_SITE_ID": "homebox",
        }
    )

    assert "DELETE FROM gateway_credential" in sql
    assert "INSERT INTO gateway_credential" in sql
    assert "DELETE FROM cloud_command WHERE status IN" in sql
    assert "'queued'" in sql
    assert "'claimed'" in sql
    assert "'running'" in sql
    assert "cloud_audit_event" not in sql


def test_refresh_db_leaves_local_db_untouched_when_dump_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _load_script()
    paths = script.paths_for(tmp_path)
    paths.logs_dir.mkdir(parents=True)
    paths.dumps_dir.mkdir(parents=True)
    paths.assets_dir.mkdir(parents=True)
    runtime = script.Runtime(
        repo_root=tmp_path,
        worktree_id="0123abcdef" * 6 + "0123",
        web_port=5173,
        api_port=8023,
        database_name="dirt_cloud_dev_0123abcdef",
        api_url="http://127.0.0.1:8023",
        web_url="http://127.0.0.1:5173",
    )
    commands: list[list[str]] = []

    monkeypatch.setattr(script, "down", lambda _paths: 0)
    monkeypatch.setattr(
        script,
        "resolve_source_database_url",
        lambda _paths: (
            "postgresql://postgres:source-secret@example.invalid:5432/railway"
        ),
    )

    def fail_dump(
        command: list[str],
        _env: dict[str, str],
        _log_path: Path,
        _cwd: Path,
        *,
        input_text: str | None = None,
    ) -> bool:
        assert input_text is None
        commands.append(command)
        return False

    monkeypatch.setattr(script, "run_logged", fail_dump)

    result = script.refresh_db(
        paths,
        runtime,
        {
            "DIRT_DEV_PG_HOST": "127.0.0.1",
            "DIRT_DEV_PG_PORT": "5432",
            "DIRT_DEV_PG_USER": "dirt",
            "DIRT_DEV_PG_PASSWORD": "local-secret",
            "DIRT_CLOUD_GATEWAY_CREDENTIAL_ID": "dev-credential",
            "DIRT_CLOUD_GATEWAY_ID": "dev-gateway",
            "DIRT_CLOUD_GATEWAY_TOKEN_SHA256": "abc123",
            "DIRT_CLOUD_SITE_ID": "homebox",
        },
    )

    captured = capsys.readouterr()
    assert result == 1
    assert len(commands) == 1
    assert commands[0][0] == "pg_dump"
    assert not any(
        command[0] in {"dropdb", "createdb", "pg_restore"} for command in commands
    )
    assert "source-secret" not in captured.err
    assert "local-secret" not in captured.err


def test_reset_uses_latest_local_dump_without_source_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _load_script()
    paths = script.paths_for(tmp_path)
    paths.logs_dir.mkdir(parents=True)
    paths.dumps_dir.mkdir(parents=True)
    older = paths.dumps_dir / "older.dump"
    newer = paths.dumps_dir / "newer.dump"
    older.write_text("older")
    newer.write_text("newer")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    runtime = script.Runtime(
        repo_root=tmp_path,
        worktree_id="0123abcdef" * 6 + "0123",
        web_port=5173,
        api_port=8023,
        database_name="dirt_cloud_dev_0123abcdef",
        api_url="http://127.0.0.1:8023",
        web_url="http://127.0.0.1:5173",
    )
    restored: list[Path] = []

    monkeypatch.setattr(script, "down", lambda _paths: 0)
    monkeypatch.setattr(
        script,
        "resolve_source_database_url",
        lambda _paths: pytest.fail("reset must not contact Railway"),
    )
    monkeypatch.setattr(
        script,
        "restore_dump",
        lambda _paths, _runtime, _env_values, dump_path, _timestamp, _binaries: (
            restored.append(dump_path) is None
        ),
    )
    monkeypatch.setattr(script, "up", lambda _paths, _runtime, _env_values: 0)

    result = script.reset(paths, runtime, {})

    assert result == 0
    assert restored == [newer]
