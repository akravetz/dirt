"""Phase timing + shell-out helper.

The phase context manager logs `=== phase NAME START` and
`=== phase NAME END elapsed=Ns (Mm:Ss)`. A grep over the kernel log gives a
per-phase wall-clock profile.
"""

from __future__ import annotations

import subprocess
import time
from contextlib import contextmanager
from pathlib import Path


def sh(cmd: str, *, cwd: Path | None = None) -> None:
    """Run a shell command, stream stdout, raise on non-zero exit."""
    print(f"$ {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True, cwd=cwd)


@contextmanager
def phase(name: str):
    """Wall-clock phase timer.

    Bracketed message format keeps phase entries greppable from upstream
    chatter (Piper progress bars, openwakeword INFO lines, tqdm output).
    """
    print(f"\n=== phase {name} START", flush=True)
    t0 = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - t0
        m, s = divmod(elapsed, 60)
        print(
            f"=== phase {name} END elapsed={elapsed:.1f}s ({int(m)}m{s:.1f}s)",
            flush=True,
        )
