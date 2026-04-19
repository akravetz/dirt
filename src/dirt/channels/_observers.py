"""Pipecat observers that emit structured log events.

Observers are non-intrusive hooks on the pipecat pipeline. Each frame pushed
between processors fires `on_push_frame`. We log every control/signal frame
to ``logs/pipecat_frames/`` (1-day retention) so turn-taking, VAD, STT, LLM,
and TTS state transitions are fully reconstructable after the fact.

Raw audio/image data frames are excluded -- they fire 20-50 times/second,
carry bytes-heavy payloads, and the individual arrivals don't add diagnostic
value beyond the aggregated durations already captured elsewhere.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from pipecat.frames.frames import (
    AudioRawFrame,
    Frame,
    HeartbeatFrame,
    ImageRawFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed

from dirt.observability import log_event

# Frame classes we deliberately DO NOT log. All are high-volume / low-signal.
_DENYLIST: tuple[type[Frame], ...] = (
    AudioRawFrame,
    ImageRawFrame,
    HeartbeatFrame,
)

# Interesting fields to extract per frame class. Observers see frames of many
# shapes; rather than maintain a per-class decoder, pick any of these field
# names that happen to exist on the frame.
_INTERESTING_FIELDS: tuple[str, ...] = (
    "text",
    "name",
    "reason",
    "command",
    "error",
    "is_error",
    "role",
    "tool_use_id",
    "function_name",
    "arguments",
    "result",
    "model",
    "stop_reason",
    "is_final",        # Deepgram InterimTranscriptionFrame
    "user_id",
    "tool_name",
)


class FrameFlowObserver(BaseObserver):
    """Log every non-raw-data frame pushed through the pipeline.

    Pass the conversation UUID in at construction — the observer captures it
    so every emitted log event can be joined against ``sessions/voice/`` by
    ``conversation_id``. (The ContextVar would work too, but this is set up
    once at pipeline start where the context is known; explicit > implicit.)
    """

    def __init__(self, conversation_id: str | None):
        super().__init__()
        self._cid = conversation_id

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if isinstance(frame, _DENYLIST):
            return

        fields = _frame_fields(frame)
        source = type(data.source).__name__ if data.source else None
        destination = type(data.destination).__name__ if data.destination else None

        log_event(
            "pipecat_frames",
            type(frame).__name__,
            conversation_id=self._cid,
            direction=str(data.direction.name) if data.direction else None,
            source=source,
            destination=destination,
            pipecat_ts_ns=data.timestamp,
            **fields,
        )


def _frame_fields(frame: Frame) -> dict[str, Any]:
    """Pull interesting fields off a frame for the log envelope.

    Walks the dataclass fields of the frame and keeps any whose name is in
    ``_INTERESTING_FIELDS``. Stringifies complex values, truncates long ones.
    """
    if not dataclasses.is_dataclass(frame):
        return {}

    out: dict[str, Any] = {}
    for f in dataclasses.fields(frame):
        if f.name not in _INTERESTING_FIELDS:
            continue
        val = getattr(frame, f.name, None)
        if val is None:
            continue
        if isinstance(val, (bytes, bytearray)):
            out[f.name] = f"<{len(val)} bytes>"
        elif isinstance(val, (str, int, float, bool)):
            out[f.name] = val
        else:
            s = str(val)
            out[f.name] = s if len(s) <= 300 else s[:300] + "…"
    return out
