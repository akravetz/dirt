"""Tests for the OTP-style hwd task supervisor."""

from __future__ import annotations

import asyncio
import time

import pytest

from dirt_hwd.supervise import supervise


@pytest.mark.asyncio
async def test_clean_return_does_not_restart() -> None:
    """A task that returns without error is terminal — supervise exits."""
    calls = 0

    async def runner(_stop_event: asyncio.Event) -> None:
        nonlocal calls
        calls += 1

    stop = asyncio.Event()
    await asyncio.wait_for(supervise("x", runner, stop), timeout=1)
    assert calls == 1


@pytest.mark.asyncio
async def test_stop_event_terminates_without_rerun() -> None:
    """If the task returns because stop_event is set, supervise exits."""
    calls = 0

    async def runner(stop_event: asyncio.Event) -> None:
        nonlocal calls
        calls += 1
        await stop_event.wait()

    stop = asyncio.Event()
    task = asyncio.create_task(supervise("x", runner, stop))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert calls == 1


@pytest.mark.asyncio
async def test_restart_on_crash_within_budget() -> None:
    """A crash inside the budget triggers a restart after backoff_s."""
    calls = 0

    async def runner(_stop_event: asyncio.Event) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError(f"boom {calls}")
        # Third call returns cleanly — supervise exits.

    stop = asyncio.Event()
    await asyncio.wait_for(
        supervise("x", runner, stop, backoff_s=0.01),
        timeout=1,
    )
    assert calls == 3


@pytest.mark.asyncio
async def test_budget_exhaustion_reraises() -> None:
    """max_restarts crashes inside window_s → supervise re-raises."""
    calls = 0

    async def runner(_stop_event: asyncio.Event) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError(f"boom {calls}")

    stop = asyncio.Event()
    with pytest.raises(RuntimeError, match="boom"):
        await asyncio.wait_for(
            supervise(
                "x",
                runner,
                stop,
                max_restarts=3,
                window_s=10.0,
                backoff_s=0.01,
            ),
            timeout=1,
        )
    assert calls == 3


@pytest.mark.asyncio
async def test_budget_slides_so_slow_crashes_are_tolerated() -> None:
    """A crash that falls out of the window resets the budget."""
    calls = 0

    async def runner(_stop_event: asyncio.Event) -> None:
        nonlocal calls
        calls += 1
        if calls <= 4:
            raise RuntimeError(f"boom {calls}")
        # Fifth call returns cleanly.

    stop = asyncio.Event()
    # window_s=0.05 is shorter than the backoff we use between crashes,
    # so the deque's oldest entry always falls out of window before we
    # hit max_restarts. Budget never exhausts.
    await asyncio.wait_for(
        supervise(
            "x",
            runner,
            stop,
            max_restarts=3,
            window_s=0.05,
            backoff_s=0.1,
        ),
        timeout=2,
    )
    assert calls == 5


@pytest.mark.asyncio
async def test_cancelled_error_propagates() -> None:
    """CancelledError must not be swallowed — cooperative shutdown."""

    async def runner(_stop_event: asyncio.Event) -> None:
        await asyncio.sleep(10)

    stop = asyncio.Event()
    task = asyncio.create_task(supervise("x", runner, stop))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_backoff_honours_stop_event() -> None:
    """During backoff sleep, setting stop_event should short-circuit."""

    async def runner(_stop_event: asyncio.Event) -> None:
        raise RuntimeError("boom")

    stop = asyncio.Event()
    task = asyncio.create_task(
        supervise("x", runner, stop, backoff_s=60.0),
    )
    # Let it crash once and enter backoff.
    await asyncio.sleep(0.05)
    assert not task.done()
    started = time.monotonic()
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    # Should return well inside the 60s backoff.
    assert time.monotonic() - started < 0.5
