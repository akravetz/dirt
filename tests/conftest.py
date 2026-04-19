"""Project-wide pytest fixtures.

The autouse :func:`isolate_observability_logs` fixture redirects
``dirt.observability.log_event`` writes to a per-test tmp directory by
setting the ``DIRT_LOGS_DIR`` environment variable. Without this, any test
that exercises code calling ``log_event`` (orchestrator, channels, services)
silently appends to the production ``logs/`` tree — polluting real
telemetry, polluting the wiki retention rotator, and making it hard to tell
test events from real ones.

This applies to every test under ``tests/`` (including the e2e suite via
fixture inheritance). Production code paths see the env var unset and fall
back to ``_DEFAULT_LOGS_DIR`` (the repo's ``logs/`` directory).
"""

from __future__ import annotations

import pytest

from dirt.observability import LOGS_DIR_ENV


@pytest.fixture(autouse=True)
def isolate_observability_logs(tmp_path, monkeypatch):
    """Point ``dirt.observability.logs_dir()`` at a per-test tmp directory.

    The env-var approach (vs monkeypatching the module's ``LOGS_DIR``
    constant) survives the writer thread reading paths lazily — every
    write resolves the env var freshly via :func:`logs_dir`.
    """
    test_logs = tmp_path / "logs"
    monkeypatch.setenv(LOGS_DIR_ENV, str(test_logs))
    yield test_logs
    # monkeypatch auto-restores the env on teardown; nothing else needed.
