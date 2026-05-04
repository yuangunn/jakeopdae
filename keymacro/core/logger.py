"""Logging configuration shared by the CLI, GUI, and tray entry points.

Every run gets a timestamped log file under ``log_dir`` (defaults to
``./logs``) so failures can be diagnosed offline. The console mirror
defaults to INFO; ``--verbose`` flips it to DEBUG.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(
    verbose: bool = False,
    log_dir: Optional[Path] = None,
    name: str = "keymacro",
) -> Optional[Path]:
    """Reconfigure the root logger and return the per-run log file path.

    Calling this more than once in the same process replaces the previous
    handlers, so it is safe to use from both the CLI bootstrap and the GUI
    bootstrap without spawning duplicates.
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    log_path: Optional[Path] = None
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"{name}_{ts}.log"
        file_h = logging.FileHandler(log_path, encoding="utf-8")
        file_h.setLevel(logging.DEBUG)
        file_h.setFormatter(fmt)
        root.addHandler(file_h)

    return log_path
