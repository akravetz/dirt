"""End-to-end training orchestrator.

Called by the docker entrypoint (apps/wake-word/docker/entrypoint.py).
Each phase is wrapped in `phase(...)` for wall-time accounting in the
run log.
"""

from __future__ import annotations

import time

from .config import TARGET_WORD, build_config
from .paths import WORKING_ROOT, expected_inputs, out_dir, verify_inputs
from .seed import prepare_seed_clips
from .timing import phase
from .train import custom_train
from .validate import validate_against_real_set
from .verify import verify_imports


def main() -> None:
    t_start = time.monotonic()
    inputs = expected_inputs(TARGET_WORD)
    out = out_dir()
    work = WORKING_ROOT

    with phase("verify_inputs"):
        verify_inputs(inputs)
    with phase("verify_imports"):
        verify_imports()
    with phase("build_config"):
        config_path = build_config(work_dir=work, out_dir=out, expected_inputs=inputs)
    with phase("prepare_seed_clips"):
        prepare_seed_clips(out_dir=out, expected_inputs=inputs)
    with phase("custom_train"):
        custom_train(
            config_path=config_path,
            work_dir=work,
            out_dir=out,
            target_word=TARGET_WORD,
        )
    with phase("validate_against_real_set"):
        validate_against_real_set(work_dir=work, out_dir=out, expected_inputs=inputs)

    total = time.monotonic() - t_start
    m, s = divmod(total, 60)
    print(f"\n=== TOTAL elapsed={total:.1f}s ({int(m)}m{s:.1f}s) ===")


if __name__ == "__main__":
    main()
