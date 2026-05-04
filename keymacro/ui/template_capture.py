"""Capture a region of the screen and save it as a template PNG.

Used by the GUI's "Capture template from region" button; takes the
trigger's region, screenshots it, writes a PNG into the macro's
``templates/`` folder, and returns the relative path so the trigger can
be updated to reference it.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import cv2  # type: ignore[import-not-found]

from ..core.capture import make_default_capturer


_BAD = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_slug(s: str) -> str:
    s = _BAD.sub("-", s.strip()).strip("-")
    return (s or "template").lower()[:48]


def capture_template(
    macro_dir: Path,
    region: tuple[int, int, int, int],
    *,
    step_id: str = "template",
    subdir: str = "templates",
) -> str:
    """Save a screenshot of ``region`` under ``macro_dir/subdir`` and return
    the path relative to ``macro_dir``."""
    x, y, w, h = region
    if w <= 0 or h <= 0:
        raise ValueError("region must have positive width and height")

    cap = make_default_capturer()
    try:
        img = cap.grab(x, y, w, h)
    finally:
        cap.close()

    target_dir = macro_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    fname = f"{_safe_slug(step_id)}_{ts}.png"
    cv2.imwrite(str(target_dir / fname), img)
    return f"{subdir}/{fname}"
