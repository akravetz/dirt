"""openWakeWord diagnostic — "hey claudia" detection through the Jabra mic.

DIAGNOSTIC MODE: logs every frame whose score exceeds LOG_FLOOR, with
timestamp, score, and a visual bar. No cooldown, no meter — just raw
event timeline so we can measure the true false-rejection rate and tune
the threshold.

Run:  uv run python training/wake-word/validation/live-test.py   (Ctrl-C to stop)
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

# File lives at training/wake-word/validation/<this>.py — 4 parents up to repo root.
ROOT = Path(__file__).resolve().parents[3]
# Override the model path with a CLI arg: `uv run python training/wake-word/validation/live-test.py var/wake-word/models/2026-04-25-v5/hey_claudia.onnx`
MODEL_PATH = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else ROOT / "var" / "wake-word" / "models" / "current" / "hey_claudia.onnx"
)

SAMPLE_RATE = 16000     # openWakeWord requires 16 kHz mono
CHUNK_MS = 80           # openWakeWord works best with 80ms frames
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)   # 1280 samples

# Diagnostic thresholds — log every frame above LOG_FLOOR; mark frames
# above DETECT_THRESHOLD as "would fire". No cooldown so we see everything.
LOG_FLOOR = 0.02
DETECT_THRESHOLD = 0.4
HEARTBEAT_EVERY = 125   # frames (~10s at 80ms/frame); prints a tick so we know it's alive


def find_jabra() -> int:
    for i, d in enumerate(sd.query_devices()):
        if "jabra" in d["name"].lower() and d["max_input_channels"] > 0:
            return i
    sys.exit("Jabra mic not found — is it plugged in?")


async def main() -> None:
    if not MODEL_PATH.exists():
        sys.exit(f"Model not found at {MODEL_PATH}")

    print(f"Loading model: {MODEL_PATH.name}")
    model = Model(wakeword_model_paths=[str(MODEL_PATH)])
    model_name = list(model.models.keys())[0]
    print(f"Loaded wake word: {model_name!r}")
    print(f"Log floor: {LOG_FLOOR}  |  Detect threshold: {DETECT_THRESHOLD}")

    jabra = find_jabra()
    print(f"Using Jabra device index: {jabra}\n")

    loop = asyncio.get_running_loop()
    audio_q: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=50)

    def mic_cb(indata, frames, time_info, status):
        if status:
            print(f"[mic] {status}", file=sys.stderr)
        # indata is int16 mono, shape (CHUNK_SAMPLES, 1) — squeeze to 1D
        frame = np.frombuffer(bytes(indata), dtype=np.int16).copy()
        with contextlib.suppress(asyncio.QueueFull, Exception):
            loop.call_soon_threadsafe(audio_q.put_nowait, frame)

    frame_count = 0
    event_count = 0
    hit_count = 0

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=CHUNK_SAMPLES,
        device=jabra,
        callback=mic_cb,
    ):
        print("listening for 'hey claudia'… Ctrl-C to stop.\n")
        print(f"{'time':<12} {'frame':>7}  {'score':>6}  bar")
        print("-" * 70)
        try:
            while True:
                frame = await audio_q.get()
                scores = model.predict(frame)
                score = scores[model_name]
                frame_count += 1

                if frame_count % HEARTBEAT_EVERY == 0:
                    ts = time.strftime("%H:%M:%S")
                    print(f"   {ts}  f={frame_count:>5}  . (heartbeat, alive)", flush=True)

                if score < LOG_FLOOR:
                    continue

                event_count += 1
                is_hit = score >= DETECT_THRESHOLD
                if is_hit:
                    hit_count += 1
                marker = "🟢" if is_hit else "  "
                ts = time.strftime("%H:%M:%S")
                bar_len = int(score * 40)
                bar = "█" * bar_len + "·" * (40 - bar_len)
                print(
                    f"{marker} {ts}  f={frame_count:>5}  {score:.3f}  {bar}",
                    flush=True,
                )

        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            print(
                f"\nsummary: {frame_count} frames, "
                f"{event_count} events above {LOG_FLOOR}, "
                f"{hit_count} above {DETECT_THRESHOLD}"
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbye")
