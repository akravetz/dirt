from __future__ import annotations

from dirt_shared.config import Settings


def test_thermoforge_connect_timeout_reads_env_alias(
    monkeypatch,
) -> None:
    monkeypatch.setenv("THERMOFORGE_CONNECT_TIMEOUT_S", "20")

    settings = Settings(_env_file=None)

    assert settings.thermoforge_connect_timeout_s == 20
