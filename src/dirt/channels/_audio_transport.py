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

import numpy as np
import sounddevice as sd
from loguru import logger

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    StartFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import BaseTransport, TransportParams


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

        def callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"[sounddevice in] {status}")
            raw = InputAudioRawFrame(
                audio=bytes(indata),
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

    def _push(self, data: bytes) -> None:
        with self._lock:
            self._ring += data

    def _pop(self, n: int) -> bytes:
        """Pop n bytes from the ring, silence-padding on underrun."""
        with self._lock:
            taken = bytes(self._ring[:n])
            del self._ring[:n]
        short = n - len(taken)
        return taken + b"\x00" * short if short else taken

    def _clear(self) -> None:
        with self._lock:
            self._ring.clear()

    def _audio_cb(self, outdata, frames, time_info, status):
        if status:
            logger.debug(f"[sounddevice out] {status}")
        outdata[:] = self._pop(len(outdata))

    async def start(self, frame: StartFrame):
        await super().start(frame)
        if self._out_stream:
            return

        self._sample_rate = self._params.audio_out_sample_rate or frame.audio_out_sample_rate

        self._out_stream = sd.RawOutputStream(
            samplerate=self._sample_rate,
            channels=self._params.audio_out_channels,
            dtype="int16",
            device=self._params.output_device,
            latency=self._params.output_latency,
            callback=self._audio_cb,
        )
        self._out_stream.start()

        await self.set_transport_ready(frame)

    async def cleanup(self):
        await super().cleanup()
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
        """
        await super().process_frame(frame, direction)
        if isinstance(frame, InterruptionFrame):
            self._clear()

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
