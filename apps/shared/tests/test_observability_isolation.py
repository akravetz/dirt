"""Verify the autouse fixture in conftest.py keeps test telemetry out of
the production ``logs/`` directory.

Without these guarantees, every test that exercises code calling
``log_event`` silently appends to the real ``logs/<stream>/<today>.jsonl``
files — polluting real telemetry and corrupting incident reconstruction.
"""

from __future__ import annotations

import time

from dirt_shared.observability import (
    _DEFAULT_LOGS_DIR,
    LOGS_DIR_ENV,
    log_event,
    logs_dir,
)


def _drain_writer(timeout_s: float = 2.0) -> None:
    """Block until the daemon writer thread has flushed all queued events.

    The writer is a single daemon thread shared across the process. After
    ``log_event`` returns, the actual disk write happens asynchronously.
    Tests that need to assert on file contents must wait for the queue
    to drain.
    """
    from dirt_shared.observability import _write_queue

    deadline = time.monotonic() + timeout_s
    while not _write_queue.empty() and time.monotonic() < deadline:
        time.sleep(0.01)
    # one extra beat to let the in-flight item finish writing
    time.sleep(0.05)


def test_logs_dir_reads_env_var(isolate_observability_logs):
    """`logs_dir()` should reflect the env var set by the autouse fixture."""
    assert logs_dir() == isolate_observability_logs
    assert logs_dir() != _DEFAULT_LOGS_DIR


def test_log_event_writes_to_tmp_not_production(isolate_observability_logs):
    """A `log_event` call inside a test must not touch the production
    `logs/` tree — proves the test-isolation contract end-to-end."""
    log_event(
        "isolation_test",
        "smoke",
        detail="if you see this in production logs the fixture is broken",
    )
    _drain_writer()

    # Tmp directory got the file.
    tmp_dir = isolate_observability_logs
    written = list(tmp_dir.rglob("*.jsonl"))
    assert len(written) == 1, f"expected 1 file in {tmp_dir}, got {written}"
    assert "isolation_test" in str(written[0])

    # Production directory got nothing for this stream.
    prod_stream_dir = _DEFAULT_LOGS_DIR / "isolation_test"
    assert not prod_stream_dir.exists(), (
        f"isolation_test stream leaked into production logs at {prod_stream_dir}"
    )


def test_log_event_captures_log_dir_at_enqueue(tmp_path, monkeypatch):
    """Async writes keep the log dir that was active at call time.

    This prevents a queued event from falling back to production logs after a
    pytest fixture restores environment variables during teardown.
    """
    first_logs = tmp_path / "first" / "logs"
    second_logs = tmp_path / "second" / "logs"

    monkeypatch.setenv(LOGS_DIR_ENV, str(first_logs))
    log_event("enqueue_path_test", "smoke")
    monkeypatch.setenv(LOGS_DIR_ENV, str(second_logs))
    _drain_writer()

    assert list((first_logs / "enqueue_path_test").glob("*.jsonl"))
    assert not (second_logs / "enqueue_path_test").exists()


def test_consecutive_tests_get_independent_dirs(
    isolate_observability_logs,
    tmp_path,
):
    """Each test invocation gets a fresh tmp_path → fresh log dir.

    Sanity check: the fixture's resolved dir lives under the test's
    tmp_path, not a shared location.
    """
    assert isolate_observability_logs == tmp_path / "logs"
