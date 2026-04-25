"""Orchestrator. Called by the Kaggle kernel shim.

The shim's job is to install runtime deps and put us on the path, then call
this `main()` — which from this point on operates entirely through the
testable library.
"""

from __future__ import annotations

import time

from .config import TARGET_WORD, build_config
from .export import export_artifacts
from .paths import KAGGLE_WORKING, expected_inputs, out_dir, verify_inputs
from .seed import prepare_seed_clips
from .timing import phase
from .train import custom_train
from .validate import validate_against_real_set
from .verify import verify_imports


def main() -> None:
    t_start = time.monotonic()
    inputs = expected_inputs(TARGET_WORD)
    out = out_dir()
    work = KAGGLE_WORKING

    with phase("verify_inputs"):
        verify_inputs(inputs)
    # NOTE: install_dependencies runs in the kernel shim BEFORE this main()
    # is imported. By the time we get here, all heavy ML deps are installed.
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
    with phase("export"):
        export_artifacts(out_dir=out, working_dir=work, target_word=TARGET_WORD)
    with phase("validate_against_real_set"):
        validate_against_real_set(work_dir=work, out_dir=out, expected_inputs=inputs)
    total = time.monotonic() - t_start
    m, s = divmod(total, 60)
    print(
        f"\n=== TOTAL elapsed={total:.1f}s ({int(m)}m{s:.1f}s)\n"
        "Training complete. Pull artifacts with: "
        "kaggle kernels output <kernel-slug>"
    )


if __name__ == "__main__":
    main()
