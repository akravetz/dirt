"""Play the RIR-capture sweep.

Runs on the device you want positioned as a "voice source" for the RIR
capture (typically your desk laptop). Plays a 15-second exponential sine
sweep through the default output device. Pair with
`training/wake-word/data-gen/capture-rir-record.py` running on the Jabra host.

Sweep parameters MUST match capture_rir_record.py exactly — the
recorder's inverse filter is derived from these constants.

Usage:
    uv run python training/wake-word/data-gen/capture-rir-play.py
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import sounddevice as sd

# MUST match capture_rir_record.py
SAMPLE_RATE = 16000
SWEEP_DURATION = 15.0
F_START = 20.0
F_END = 7800.0


def generate_sweep(duration: float, sr: int, f1: float, f2: float) -> np.ndarray:
    """Exponential sine sweep, Farina (2000). Mono float32."""
    n = int(duration * sr)
    t = np.arange(n, dtype=np.float64) / sr
    R = np.log(f2 / f1)
    sweep = np.sin(2 * np.pi * f1 * duration / R * (np.exp(t * R / duration) - 1))
    return sweep.astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser(description="Play the RIR-capture sweep.")
    ap.add_argument(
        "--gain",
        type=float,
        default=0.8,
        help="playback gain 0-1 (default 0.8). Raise if SNR is low on record side.",
    )
    ap.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="seconds to wait before playing (gives you time to step back).",
    )
    args = ap.parse_args()

    sweep = generate_sweep(SWEEP_DURATION, SAMPLE_RATE, F_START, F_END) * args.gain

    out_idx = sd.default.device[1]
    print(f"Output device: {sd.query_devices(out_idx)['name']}")
    print(f"Sweep: {SWEEP_DURATION:.1f}s, {F_START:.0f}–{F_END:.0f} Hz, gain={args.gain}")
    print()
    print(f"Playing in {args.delay:.0f}s — step back if needed so you're not in the path.")
    for i in range(int(args.delay), 0, -1):
        print(f"  {i}")
        time.sleep(1)

    print("Playing sweep... (don't move)")
    sd.play(sweep, samplerate=SAMPLE_RATE, device=out_idx)
    sd.wait()
    print("Done. Check the recorder host for results.")


if __name__ == "__main__":
    main()
