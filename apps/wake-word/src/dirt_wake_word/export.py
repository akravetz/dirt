"""ONNX → tflite via onnx2tf (replaces upstream's broken onnx_tf path).

Also surfaces the .onnx and .tflite at the /kaggle/working/ root so they
appear as prominent outputs in the kernel UI and in `kaggle kernels output`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .timing import sh


def export_artifacts(*, out_dir: Path, working_dir: Path, target_word: str) -> None:
    onnx_path = out_dir / f"{target_word}.onnx"
    float32_tflite = out_dir / f"{target_word}_float32.tflite"
    final_tflite = out_dir / f"{target_word}.tflite"

    sh(f"onnx2tf -i {onnx_path} -o {out_dir} -kat onnx____Flatten_0")
    if float32_tflite.exists():
        shutil.move(str(float32_tflite), str(final_tflite))

    for src in (onnx_path, final_tflite):
        if src.exists():
            shutil.copy(src, working_dir / src.name)
            print(f"Published -> {working_dir / src.name}")
