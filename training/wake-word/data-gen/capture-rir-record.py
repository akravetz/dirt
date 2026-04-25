"""Record a room-impulse-response sweep through the Jabra.

Runs on the host the Jabra is plugged into. Records for a fixed window,
during which the user plays the matching sweep from a different device
(laptop, phone, Bluetooth speaker) positioned where they'd typically
speak from. After recording, deconvolves with the sweep's inverse filter
to recover the impulse response of (room + Jabra).

Flow:
    1. On the Jabra host:  uv run python training/wake-word/data-gen/capture-rir-record.py desk
       → counts down, records for RECORD_SECONDS
    2. On the laptop (or other source device):
       uv run python training/wake-word/data-gen/capture-rir-play.py
       → plays the matching sweep
    3. The record script deconvolves after the window ends and saves the IR.

The deconvolution is time-invariant — it doesn't matter when within the
recording window the sweep actually starts, as long as it finishes before
the window ends. The IR peak auto-locates the direct-path arrival.

Drop the resulting files in var/wake-word/rirs/ into openWakeWord's `rir_paths`.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from scipy.signal import fftconvolve

# These MUST match capture_rir_play.py exactly.
SAMPLE_RATE = 16000
SWEEP_DURATION = 15.0
F_START = 20.0
F_END = 7800.0

# Recording window — long enough that the user has time to alt-tab to the
# laptop and start the player after kicking off the recorder.
RECORD_SECONDS = 45.0

IR_KEEP_MS = 1500           # trim IR to this many ms after direct-path peak
IR_LEAD_MS = 5              # keep this many ms before the peak

# File lives at training/wake-word/data-gen/<this>.py — 4 parents up to repo root.
ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "var" / "wake-word" / "rirs-raw"
IR_DIR = ROOT / "var" / "wake-word" / "rirs"


def find_jabra() -> int:
    for i, d in enumerate(sd.query_devices()):
        if "jabra" in d["name"].lower() and d["max_input_channels"] > 0:
            return i
    sys.exit("Jabra mic not found — is it plugged in?")


def generate_ess(
    duration: float, sr: int, f1: float, f2: float
) -> tuple[np.ndarray, np.ndarray]:
    """Exponential sine sweep + its inverse filter (Farina 2000)."""
    n = int(duration * sr)
    t = np.arange(n, dtype=np.float64) / sr
    R = np.log(f2 / f1)
    sweep = np.sin(2 * np.pi * f1 * duration / R * (np.exp(t * R / duration) - 1))
    envelope = np.exp(-t * R / duration)
    inverse = sweep[::-1] * envelope
    inverse = inverse / np.sqrt(np.sum(inverse ** 2))
    return sweep.astype(np.float32), inverse.astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser(description="Record a sweep-based RIR.")
    ap.add_argument("label", help="position label, e.g. 'desk' or 'across_room'")
    ap.add_argument(
        "--seconds",
        type=float,
        default=RECORD_SECONDS,
        help=f"recording window (default {RECORD_SECONDS:.0f}s)",
    )
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    IR_DIR.mkdir(parents=True, exist_ok=True)

    jabra = find_jabra()
    print(f"Jabra mic: device {jabra} — {sd.query_devices(jabra)['name']}")
    print(f"Position label: {args.label}")
    print(f"Recording window: {args.seconds:.0f}s")
    print()
    print("INSTRUCTIONS:")
    print("  1. Position your laptop (or Bluetooth speaker) at the target position")
    print("     with its speaker pointing toward the Jabra.")
    print("  2. Set laptop volume to 70-80%.")
    print("  3. When recording starts, go to the laptop and run:")
    print("         uv run python training/wake-word/data-gen/capture-rir-play.py")
    print("  4. Stay still. Try not to be in the path between speaker and Jabra.")
    print()
    print("Starting in 3...")
    for i in (3, 2, 1):
        print(f"  {i}")
        time.sleep(1)

    total_samples = int(args.seconds * SAMPLE_RATE)
    print(f"Recording for {args.seconds:.0f}s — RUN THE PLAYER NOW")
    recording = sd.rec(
        total_samples,
        samplerate=SAMPLE_RATE,
        channels=1,
        device=jabra,
        dtype="float32",
    )
    # Progress dots
    t_start = time.monotonic()
    while time.monotonic() - t_start < args.seconds:
        elapsed = time.monotonic() - t_start
        print(f"\r  {elapsed:5.1f}s / {args.seconds:.0f}s", end="", flush=True)
        time.sleep(0.25)
    sd.wait()
    print("\n...recording complete.\n")

    recording = recording.squeeze()

    # Save the raw recording for archival / reprocessing
    raw_path = RAW_DIR / f"{args.label}.wav"
    wavfile.write(raw_path, SAMPLE_RATE, (recording * 32767).astype(np.int16))
    print(f"Raw recording: {raw_path}")

    # Build matching sweep + inverse filter for deconvolution
    _sweep, inverse = generate_ess(SWEEP_DURATION, SAMPLE_RATE, F_START, F_END)

    print("Deconvolving...")
    ir_full = fftconvolve(recording, inverse, mode="full")
    peak_idx = int(np.argmax(np.abs(ir_full)))
    peak_time_s = peak_idx / SAMPLE_RATE
    print(f"  direct-path peak at t = {peak_time_s:.2f}s in the deconvolution output")

    pre = int(IR_LEAD_MS / 1000 * SAMPLE_RATE)
    post = int(IR_KEEP_MS / 1000 * SAMPLE_RATE)
    start = max(peak_idx - pre, 0)
    end = min(peak_idx + post, len(ir_full))
    ir = ir_full[start:end].astype(np.float32)

    peak = float(np.max(np.abs(ir)))
    if peak > 0:
        ir = ir / peak * 0.95

    ir_path = IR_DIR / f"{args.label}.wav"
    wavfile.write(ir_path, SAMPLE_RATE, (ir * 32767).astype(np.int16))
    print(f"Impulse response: {ir_path}  ({len(ir) / SAMPLE_RATE * 1000:.0f}ms)")

    # SNR estimate: find the sweep's actual location, compare signal to
    # surrounding silence. A rough proxy: compare peak of deconvolved IR
    # to the RMS of the tail (long after direct path — should be reverb
    # decay plus noise).
    tail_start = min(end + int(0.5 * SAMPLE_RATE), len(ir_full) - int(0.5 * SAMPLE_RATE))
    tail = ir_full[tail_start : tail_start + int(0.5 * SAMPLE_RATE)]
    noise_rms = float(np.sqrt(np.mean(tail ** 2))) + 1e-9
    peak_abs = float(np.max(np.abs(ir_full)))
    snr_db = 20 * np.log10(peak_abs / noise_rms)
    print(f"SNR estimate (peak-vs-tail): {snr_db:.1f} dB")
    if snr_db < 20:
        print("  ⚠️  Low SNR. Play louder, move speaker closer, or quiet the room.")
    elif snr_db > 40:
        print("  ✅  Clean capture.")
    else:
        print("  👍  Acceptable.")

    # Also warn if the sweep didn't seem to register at all
    if peak_abs < 0.5:
        print("  ⚠️  Peak amplitude is low — did the player actually run?")


if __name__ == "__main__":
    main()
