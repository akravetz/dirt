"""Single source of truth for the four training-data subset directory names
and the seed-clip filename prefixes.

These were duplicated as raw string literals across seed.py, augment.py,
tts_cache.py, and the docker entrypoint. Any rename has to land
simultaneously in all four; consolidating here makes that mechanical.
"""

from __future__ import annotations

# The four directories openwakeword's --generate_clips populates and the
# augment+features step reads from. Iteration order matters: train sets
# must be in place before test sets (validate.py relies on positive_test
# existing to compute total_length).
SUBSETS: tuple[str, ...] = (
    "positive_train",
    "negative_train",
    "positive_test",
    "negative_test",
)

# Filename-prefix conventions set by `seed.prepare_seed_clips`. Augment uses
# the prefix to decide which augmentation pipeline applies (real-room
# recordings skip the RIR convolution because they already carry one in).
PREFIX_SYNTH_CLONE = "synth_clone_"
PREFIX_REALMIC_POS = "realmic_pos_"
PREFIX_SYNTH_NEIGHBOR = "synth_neighbor_"
PREFIX_REALMIC_NEG = "realmic_neg_"

REAL_AUDIO_PREFIXES: tuple[str, ...] = (
    PREFIX_REALMIC_POS,
    PREFIX_REALMIC_NEG,
)


def is_real_audio(filename: str) -> bool:
    """True if filename was recorded in a real room (skip synthetic RIR)."""
    return filename.startswith(REAL_AUDIO_PREFIXES)
