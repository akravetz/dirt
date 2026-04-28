"""Capture real-mic samples for wake-word training + validation.

Records continuously from the Jabra mic to one long WAV, then segments it
with silero-vad into individual utterance clips. Use for collecting both
positive samples (real "hey Claudia" utterances at varied positions and
voices) and negative samples (varied phrases that aren't the wake word).

VAD-based segmentation distinguishes speech from non-speech using a neural
model, so it works in noisy conditions (TV, music, kitchen sounds) where
the older RMS-silence approach would treat the whole recording as one big
clip or cut at false silences in the music.

Workflow:
    1. Run with --label realmic-pos (or whatever).
    2. Script announces "listening" and starts recording.
    3. Speak utterances naturally — pauses can be short, background can
       be loud. silero-vad finds the speech regions after the fact.
    4. Ctrl-C when done.
    5. Script post-processes the recording, writes:
        var/wake-word/realmic-stage/<TS>/<label>_NNN.wav   one per utterance
        var/wake-word/realmic-stage/<TS>/_full-recording.wav     kept for re-segmenting
        var/wake-word/realmic-stage/<TS>/segments.csv      timing audit

Tip: review the extracted clips with `scripts/audio-review` before promoting
into var/wake-word/voice-clones/, neighbors/, or validation/.

silero-vad is not a regular dirt-wake-word dep (it pulls a 2 GB CUDA
torch stack). Invoke with `uv run --with silero-vad` so the trainer
image stays lean:

    uv run --with silero-vad python apps/wake-word/data-gen/capture-realmic.py --label realmic-pos
    uv run --with silero-vad python apps/wake-word/data-gen/capture-realmic.py --label realmic-neg

Re-segment an existing recording with a different threshold:
    uv run --with silero-vad python apps/wake-word/data-gen/capture-realmic.py \
        --out-dir var/wake-word/realmic-stage/<TS> --vad-threshold 0.4
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

# File lives at apps/wake-word/data-gen/<this>.py — 4 parents up to repo root.
ROOT = Path(__file__).resolve().parents[3]

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM

DEFAULT_VAD_THRESHOLD = 0.5  # silero-vad confidence cutoff (0-1)
SPEECH_PAD_MS = 200  # padding around each detected utterance
MIN_SPEECH_DURATION_MS = 250  # drop sub-quarter-second pops as not-speech


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
        f"listening on Jabra (device {device}) — speak naturally; pauses can "
        "be short and background can be loud. Ctrl-C to stop.",
        flush=True,
    )

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.int16,
        device=device,
        callback=callback,
        blocksize=SAMPLE_RATE // 10,  # 100 ms blocks
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
    print(f"  wrote {target_path.name} ({duration:.1f}s, {len(audio) / 1e6:.1f} Msamples)")
    return target_path


def find_utterances_vad(audio: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    """Return (start_sample, end_sample) for each detected utterance using
    silero-vad. Padding (SPEECH_PAD_MS on each side) is applied by the VAD
    itself; clamping to clip bounds is handled by the segmenter.
    """
    try:
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad
    except ImportError:
        sys.exit(
            "silero-vad not available. Re-run with:\n"
            "  uv run --with silero-vad python apps/wake-word/data-gen/capture-realmic.py ..."
        )

    audio_tensor = torch.from_numpy(audio.astype(np.float32) / 32768.0)
    model = load_silero_vad()
    timestamps = get_speech_timestamps(
        audio_tensor,
        model,
        sampling_rate=SAMPLE_RATE,
        threshold=threshold,
        min_speech_duration_ms=MIN_SPEECH_DURATION_MS,
        speech_pad_ms=SPEECH_PAD_MS,
    )
    return [(int(ts["start"]), int(ts["end"])) for ts in timestamps]


def segment_and_extract(
    full_wav: Path, out_dir: Path, label: str, vad_threshold: float
) -> int:
    """Split the long recording into per-utterance WAVs + write segments.csv."""
    with wave.open(str(full_wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)

    utterances = find_utterances_vad(audio, vad_threshold)
    if not utterances:
        print(
            f"no utterances found at vad_threshold={vad_threshold} — "
            "try a lower value (e.g. 0.3) for quieter speech",
            file=sys.stderr,
        )
        return 0

    csv_path = out_dir / "segments.csv"
    with csv_path.open("w") as f:
        wr = csv.writer(f)
        wr.writerow(["index", "filename", "start_s", "duration_s"])
        print(f"\nextracting {len(utterances)} utterances → {out_dir}/")
        for idx, (start, end) in enumerate(utterances, start=1):
            clip = audio[start:end]
            fname = f"{label}_{idx:03d}.wav"
            with wave.open(str(out_dir / fname), "wb") as w:
                w.setnchannels(CHANNELS)
                w.setsampwidth(SAMPLE_WIDTH)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(clip.tobytes())
            duration = (end - start) / SAMPLE_RATE
            offset = start / SAMPLE_RATE
            wr.writerow([idx, fname, f"{offset:.2f}", f"{duration:.2f}"])
            print(f"  {fname}  @{offset:6.1f}s  +{duration:.2f}s")
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
        help="Output dir (default: var/wake-word/realmic-stage/<timestamp>/). "
        "Pointing at an existing dir re-segments its _full-recording.wav "
        "without re-recording.",
    )
    p.add_argument(
        "--vad-threshold",
        type=float,
        default=DEFAULT_VAD_THRESHOLD,
        help=f"silero-vad speech-confidence cutoff (0-1). "
        f"Lower → more permissive. Default {DEFAULT_VAD_THRESHOLD}.",
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
    if full_wav.exists() and args.out_dir is not None:
        print(f"re-segmenting existing {full_wav.name} (skipping record)", flush=True)
    else:
        record_until_sigint(find_jabra(), full_wav)

    n = segment_and_extract(full_wav, out_dir, args.label, args.vad_threshold)
    print(
        f"\nDone. {n} utterances extracted to {out_dir}/\n"
        f"Review with: uv run python scripts/audio-review.py {out_dir}\n"
        f"Re-segment with a different VAD threshold (full recording kept):\n"
        f"  uv run --with silero-vad python apps/wake-word/data-gen/capture-realmic.py "
        f"--out-dir {out_dir} --vad-threshold <new>"
    )


if __name__ == "__main__":
    main()
