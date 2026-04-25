"""Capture real-mic samples for wake-word training + validation.

Records continuously from the Jabra mic to one long WAV, then segments it on
silence (≥2 s gap) into individual utterance clips. Use for collecting both
positive samples (real "hey Claudia" utterances at varied positions/voices)
and negative samples (varied phrases that aren't the wake word).

Workflow:
    1. Run with --label realmic-pos (or whatever).
    2. Script announces "listening" and starts recording.
    3. Speak a phrase, pause ≥2 s, speak another, pause, etc.
       The 2-s gap is the segmentation signal — be deliberate about quiet pauses.
    4. Ctrl-C when done.
    5. Script post-processes the recording, writes:
        var/wake-word/realmic-stage/<TS>/<label>_NNN.wav   one per utterance
        var/wake-word/realmic-stage/<TS>/_full-recording.wav     kept for re-segmenting
        var/wake-word/realmic-stage/<TS>/segments.csv      timing + peak RMS audit

Tip: review the extracted clips with `scripts/audio-review` before promoting
into var/wake-word/voice-clones/, neighbors/, or validation/.

Usage:
    uv run python training/wake-word/data-gen/capture-realmic.py --label realmic-pos
    uv run python training/wake-word/data-gen/capture-realmic.py --label realmic-neg
    uv run python training/wake-word/data-gen/capture-realmic.py --label me-far --silence-rms 350
"""

from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd

# File lives at training/wake-word/data-gen/<this>.py — 4 parents up to repo root.
ROOT = Path(__file__).resolve().parents[3]

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM

# VAD knobs (tune via CLI if room is unusual)
FRAME_MS = 100
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 1600
DEFAULT_SILENCE_RMS = 250  # int16 RMS; floor of typical Jabra noise
MIN_SILENCE_FRAMES = 20  # 20 × 100 ms = 2.0 s — the segmentation gap
LEAD_MS = 150  # padding before each detected utterance
TAIL_MS = 200  # padding after


def find_jabra() -> int:
    for i, d in enumerate(sd.query_devices()):
        if "jabra" in d["name"].lower() and d["max_input_channels"] > 0:
            return i
    sys.exit("Jabra mic not found — is it plugged in?")


def record_until_sigint(device: int, target_path: Path) -> Path:
    """Record continuously to a WAV until SIGINT. Return the WAV path."""
    chunks: list[np.ndarray] = []

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[mic] {status}", file=sys.stderr)
        chunks.append(indata.copy())

    interrupted = False

    def handle_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, handle_sigint)

    print(
        f"listening on Jabra (device {device}) — speak phrases with ≥2 s gaps. "
        "Ctrl-C to stop.",
        flush=True,
    )

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.int16,
        device=device,
        callback=callback,
        blocksize=FRAME_SAMPLES,
    ):
        elapsed = 0
        while not interrupted:
            time.sleep(1.0)
            elapsed += 1
            if elapsed % 10 == 0:
                print(f"  ...{elapsed}s recorded", flush=True)

    print("stopped, writing recording...", flush=True)
    if not chunks:
        sys.exit("no audio captured")

    audio = np.concatenate(chunks).flatten().astype(np.int16)
    with wave.open(str(target_path), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio.tobytes())
    duration = len(audio) / SAMPLE_RATE
    print(f"  wrote {target_path.name} ({duration:.1f}s, {len(audio)/1e6:.1f} Msamples)")
    return target_path


def find_utterances(audio: np.ndarray, threshold: int) -> list[tuple[int, int, float]]:
    """Return (start_frame, end_frame, peak_rms) for each detected utterance.

    Frames are FRAME_SAMPLES wide. An utterance is a contiguous run of
    above-threshold frames; runs are split when ≥MIN_SILENCE_FRAMES of
    consecutive below-threshold frames appear.
    """
    n_frames = len(audio) // FRAME_SAMPLES
    if n_frames == 0:
        return []
    frames = audio[: n_frames * FRAME_SAMPLES].reshape(n_frames, FRAME_SAMPLES)
    rms = np.sqrt(np.mean(frames.astype(np.float32) ** 2, axis=1))
    is_active = rms > threshold

    utterances: list[tuple[int, int, float]] = []
    i = 0
    while i < n_frames:
        if not is_active[i]:
            i += 1
            continue
        start = i
        last_active = i
        silent_run = 0
        while i < n_frames:
            if is_active[i]:
                last_active = i
                silent_run = 0
            else:
                silent_run += 1
                if silent_run >= MIN_SILENCE_FRAMES:
                    break
            i += 1
        peak = float(rms[start : last_active + 1].max())
        utterances.append((start, last_active, peak))
        # Skip past the silence so we don't re-enter the same utterance
        i = last_active + silent_run + 1
    return utterances


def segment_and_extract(
    full_wav: Path, out_dir: Path, label: str, threshold: int
) -> int:
    """Split the long recording into per-utterance WAVs + write segments.csv."""
    with wave.open(str(full_wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    utterances = find_utterances(audio, threshold)
    if not utterances:
        print(f"no utterances found at threshold={threshold} — try a lower value", file=sys.stderr)
        return 0

    lead = LEAD_MS * SAMPLE_RATE // 1000
    tail = TAIL_MS * SAMPLE_RATE // 1000
    csv_path = out_dir / "segments.csv"

    with csv_path.open("w") as f:
        wr = csv.writer(f)
        wr.writerow(["index", "filename", "start_s", "duration_s", "peak_rms"])
        print(f"\nextracting {len(utterances)} utterances → {out_dir}/")
        for idx, (start_frame, end_frame, peak) in enumerate(utterances, start=1):
            sample_start = max(0, start_frame * FRAME_SAMPLES - lead)
            sample_end = min(len(audio), (end_frame + 1) * FRAME_SAMPLES + tail)
            clip = audio[sample_start:sample_end]
            fname = f"{label}_{idx:03d}.wav"
            with wave.open(str(out_dir / fname), "wb") as w:
                w.setnchannels(CHANNELS)
                w.setsampwidth(SAMPLE_WIDTH)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(clip.tobytes())
            duration = (sample_end - sample_start) / SAMPLE_RATE
            offset = sample_start / SAMPLE_RATE
            wr.writerow([idx, fname, f"{offset:.2f}", f"{duration:.2f}", f"{peak:.0f}"])
            print(f"  {fname}  @{offset:6.1f}s  +{duration:.2f}s  peak_rms={peak:.0f}")
    return len(utterances)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--label",
        default="realmic",
        help="Filename prefix for extracted clips (default: 'realmic').",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output dir (default: var/wake-word/realmic-stage/<timestamp>/).",
    )
    p.add_argument(
        "--silence-rms",
        type=int,
        default=DEFAULT_SILENCE_RMS,
        help=f"Frames with RMS below this count as silence. Default {DEFAULT_SILENCE_RMS}.",
    )
    args = p.parse_args()

    out_dir = args.out_dir or (
        ROOT
        / "var"
        / "wake-word"
        / "realmic-stage"
        / datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    full_wav = out_dir / "_full-recording.wav"
    record_until_sigint(find_jabra(), full_wav)

    n = segment_and_extract(full_wav, out_dir, args.label, args.silence_rms)
    print(
        f"\nDone. {n} utterances extracted to {out_dir}/\n"
        f"Review with: uv run python scripts/audio-review.py {out_dir}\n"
        f"Re-segment with a different threshold (full recording kept):\n"
        f"  uv run python training/wake-word/data-gen/capture-realmic.py "
        f"--out-dir {out_dir} --silence-rms <new>"
    )


if __name__ == "__main__":
    main()
