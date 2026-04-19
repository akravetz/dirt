"""Pipecat transport backed by python-sounddevice in callback mode.

Callback mode decouples the pipeline clock from the audio hardware clock.
PortAudio calls `_audio_cb` whenever it needs samples; our asyncio pipeline
pushes into a thread-safe ring buffer whenever it gets scheduled. The ring
absorbs Python/asyncio jitter so the portaudio buffer can stay small
(`latency='low'`) without xrunning, and barge-in is truly instant — on
`InterruptionFrame` we just clear the ring buffer, one memory op.

Why not `sd.RawOutputStream.write()` (push mode)? That couples the pipeline
to the hardware clock: if our Python loop is late for even a few ms, the
ALSA buffer starves and you get xruns. Callback mode inverts control.

Jabra-specific knobs beyond what Pipecat's `LocalAudioTransport` offers:

    - `playback_gain_db` : scalar pre-gain (Jabra speaker is quiet at unity)
    - channel upmix      : if stream opens more channels than the frame has,
                           duplicate samples across them (Jabra's USB endpoint
                           is stereo-only; TTS produces mono)

"""

from __future__ import annotations

import asyncio
import threading
import time

import numpy as np
import sounddevice as sd
from loguru import logger

from pipecat.frames.frames import (
    BotSpeakingFrame,
    Frame,
    FunctionCallResultFrame,
    FunctionCallsStartedFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    StartFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import BaseTransport, TransportParams

from dirt.observability import CONVERSATION_ID, log_event

# Log input amplitude at roughly this rate (Hz). 20ms blocksize means every
# 50th frame = 1 Hz. Low enough not to flood logs/audio_rms/, high enough to
# see when the user started speaking and whether audio went silent during
# TTS playback.
_RMS_LOG_EVERY_N_FRAMES = 50


class SoundDeviceTransportParams(TransportParams):
    input_device: int | str | None = None
    output_device: int | str | None = None
    playback_gain_db: float = 0.0
    # Portaudio output buffer target (seconds, or "low"/"high"). In callback
    # mode, 'low' is safe — the ring buffer absorbs pipeline jitter.
    output_latency: str | float = "low"


class SoundDeviceInputTransport(BaseInputTransport):
    _params: SoundDeviceTransportParams

    def __init__(self, params: SoundDeviceTransportParams):
        super().__init__(params)
        self._in_stream: sd.RawInputStream | None = None
        self._sample_rate = 0

    async def start(self, frame: StartFrame):
        await super().start(frame)
        if self._in_stream:
            return

        self._sample_rate = self._params.audio_in_sample_rate or frame.audio_in_sample_rate
        blocksize = int(self._sample_rate * 0.02)  # 20 ms
        loop = self.get_event_loop()

        # Portaudio runs `callback` on a C-spawned thread — Python
        # contextvars do NOT propagate there. Capture the conversation_id
        # in the asyncio context at stream start, then pass it explicitly
        # when logging from the callback.
        cid = CONVERSATION_ID.get()
        rms_counter = [0]

        def callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"[sounddevice in] {status}")
            raw_bytes = bytes(indata)

            # Decimated amplitude trace — see _RMS_LOG_EVERY_N_FRAMES.
            rms_counter[0] += 1
            if rms_counter[0] >= _RMS_LOG_EVERY_N_FRAMES:
                rms_counter[0] = 0
                pcm = np.frombuffer(raw_bytes, dtype=np.int16)
                if pcm.size > 0:
                    rms = int(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
                    log_event(
                        "audio_rms", "rms",
                        conversation_id=cid,
                        rms=rms,
                    )

            raw = InputAudioRawFrame(
                audio=raw_bytes,
                sample_rate=self._sample_rate,
                num_channels=self._params.audio_in_channels,
            )
            asyncio.run_coroutine_threadsafe(self.push_audio_frame(raw), loop)

        self._in_stream = sd.RawInputStream(
            samplerate=self._sample_rate,
            channels=self._params.audio_in_channels,
            dtype="int16",
            blocksize=blocksize,
            device=self._params.input_device,
            callback=callback,
        )
        self._in_stream.start()

        await self.set_transport_ready(frame)

    async def cleanup(self):
        await super().cleanup()
        if self._in_stream:
            self._in_stream.stop()
            self._in_stream.close()
            self._in_stream = None


class SoundDeviceOutputTransport(BaseOutputTransport):
    _params: SoundDeviceTransportParams

    def __init__(self, params: SoundDeviceTransportParams):
        super().__init__(params)
        self._out_stream: sd.RawOutputStream | None = None
        self._sample_rate = 0
        self._gain = 10 ** (params.playback_gain_db / 20)

        # Thread-safe ring buffer. The portaudio audio thread pops from here at
        # exactly the hardware clock rate; write_audio_frame (on the asyncio
        # loop) pushes whenever Pipecat schedules audio.
        self._ring = bytearray()
        self._lock = threading.Lock()

        # Per-assistant-turn timing. Measures the decoupling between what
        # pipecat thinks ("TTS done streaming") and what the user hears
        # ("speaker actually finished"). Written to logs/audio_playback/.
        self._cid: str | None = None
        self._turn_start_ts: float | None = None  # first write after empty ring
        self._tts_stopped_ts: float | None = None  # TTSStoppedFrame received

        # Keeps pipecat's idle timer honest. Pipecat's own `BotSpeakingFrame`
        # emission is driven by incoming TTS audio frames -- when TTS streams
        # faster than real-time (ElevenLabs turbo dumps 13s of audio in 3s),
        # all frames arrive in one burst and the idle timer never gets reset
        # after the first one. Our keepalive task fires the same frame every
        # 0.2s as long as the ring still has audio, so idle tracks the actual
        # playback tail rather than the TTS-streaming tail.
        #
        # Also fires during tool-call execution. FunctionCallsStartedFrame
        # fires once at the start of a tool call and FunctionCallResultFrame
        # once at the end -- nothing in between -- so without this, idle would
        # fire 15s into a slow tool and cut the pipeline while the LLM is
        # legitimately waiting on a result.
        self._keepalive_task: asyncio.Task | None = None
        self._tool_in_progress: bool = False

    def _push(self, data: bytes) -> None:
        with self._lock:
            self._ring += data

    def _pop(self, n: int) -> bytes:
        """Pop n bytes from the ring, silence-padding on underrun. Emit a
        turn-complete event the moment the ring drains after TTS finished."""
        with self._lock:
            taken = bytes(self._ring[:n])
            del self._ring[:n]
            now_empty = len(self._ring) == 0
        short = n - len(taken)
        result = taken + b"\x00" * short if short else taken

        # If ring just drained AND we have a pending TTS-stopped marker, that's
        # the moment the user physically stops hearing Claudia. Emit once,
        # reset the timers. Happens on the portaudio C thread — log_event is
        # thread-safe (one-append writes).
        if (
            now_empty
            and self._tts_stopped_ts is not None
            and self._turn_start_ts is not None
        ):
            t_end = time.monotonic()
            log_event(
                "audio_playback",
                "turn_complete",
                conversation_id=self._cid,
                tts_stream_duration_s=round(self._tts_stopped_ts - self._turn_start_ts, 3),
                playback_duration_s=round(t_end - self._turn_start_ts, 3),
                excess_buffer_s=round(t_end - self._tts_stopped_ts, 3),
            )
            self._turn_start_ts = None
            self._tts_stopped_ts = None

        return result

    def _clear(self) -> None:
        with self._lock:
            self._ring.clear()
        # Barge-in or cancel — any in-flight turn metric is now meaningless.
        self._turn_start_ts = None
        self._tts_stopped_ts = None

    def _audio_cb(self, outdata, frames, time_info, status):
        if status:
            logger.debug(f"[sounddevice out] {status}")
        outdata[:] = self._pop(len(outdata))

    async def start(self, frame: StartFrame):
        await super().start(frame)
        if self._out_stream:
            return

        self._sample_rate = self._params.audio_out_sample_rate or frame.audio_out_sample_rate
        # Capture the conversation id now (asyncio context); the portaudio
        # callback runs on a C thread where the ContextVar isn't propagated.
        self._cid = CONVERSATION_ID.get()

        self._out_stream = sd.RawOutputStream(
            samplerate=self._sample_rate,
            channels=self._params.audio_out_channels,
            dtype="int16",
            device=self._params.output_device,
            latency=self._params.output_latency,
            callback=self._audio_cb,
        )
        self._out_stream.start()

        self._keepalive_task = asyncio.create_task(self._bot_speaking_keepalive())

        await self.set_transport_ready(frame)

    async def _bot_speaking_keepalive(self) -> None:
        """Broadcast `BotSpeakingFrame` every 0.2s while the pipeline is
        actively working on behalf of the user, so pipecat's idle timer
        doesn't fire mid-work.

        "Actively working" = ring buffer has audio queued, OR a tool call
        is in progress. Both are states where pipecat's built-in
        BotSpeakingFrame emission stops (audio-frame burst ends, or the
        tool handler is awaiting), but the conversation is not actually
        idle from the user's perspective.
        """
        try:
            while True:
                await asyncio.sleep(0.2)
                with self._lock:
                    playing = len(self._ring) > 0
                if playing or self._tool_in_progress:
                    await self.broadcast_frame(BotSpeakingFrame)
        except asyncio.CancelledError:
            pass

    async def cleanup(self):
        await super().cleanup()
        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None
        if self._out_stream:
            self._out_stream.stop()
            self._out_stream.close()
            self._out_stream = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """On barge-in, clear the ring buffer — instant flush, one memcpy.

        Mirrors `LiveKitOutputTransport.process_frame` (clear_queue) and
        `FastAPIWebsocketOutputTransport.process_frame` (clear audio_send_buffer).
        Pipecat's base class cancels its pipeline-level audio task; we clear
        the transport-specific buffer it can't see.

        Also marks the TTS-stopped timestamp for the turn-duration metric.
        """
        await super().process_frame(frame, direction)
        if isinstance(frame, InterruptionFrame):
            self._clear()
        elif isinstance(frame, TTSStoppedFrame):
            self._tts_stopped_ts = time.monotonic()
        elif isinstance(frame, FunctionCallsStartedFrame):
            self._tool_in_progress = True
        elif isinstance(frame, FunctionCallResultFrame):
            self._tool_in_progress = False

    async def write_audio_frame(self, frame: OutputAudioRawFrame) -> bool:
        if not self._out_stream:
            return False

        pcm = np.frombuffer(frame.audio, dtype=np.int16)

        # Upmix if the stream opens more channels than the frame carries —
        # Jabra's playback endpoint is stereo-only; TTS frames are mono.
        out_channels = self._params.audio_out_channels
        if frame.num_channels == 1 and out_channels > 1:
            pcm = np.repeat(pcm[:, None], out_channels, axis=1).reshape(-1)

        if self._gain != 1.0:
            boosted = pcm.astype(np.float32) * self._gain
            np.clip(boosted, -32768, 32767, out=boosted)
            pcm = boosted.astype(np.int16)

        # First write after the ring drained = start of a new assistant turn.
        if self._turn_start_ts is None:
            self._turn_start_ts = time.monotonic()

        self._push(pcm.tobytes())
        return True


class SoundDeviceTransport(BaseTransport):
    def __init__(self, params: SoundDeviceTransportParams):
        super().__init__()
        self._params = params
        self._input = SoundDeviceInputTransport(params) if params.audio_in_enabled else None
        self._output = SoundDeviceOutputTransport(params) if params.audio_out_enabled else None

    def input(self) -> FrameProcessor:
        if not self._input:
            raise RuntimeError("audio_in_enabled=False — no input transport")
        return self._input

    def output(self) -> FrameProcessor:
        if not self._output:
            raise RuntimeError("audio_out_enabled=False — no output transport")
        return self._output
