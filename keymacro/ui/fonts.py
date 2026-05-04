"""Application-bundled fonts.

Registers the four Noto Sans KR weights shipped in
``keymacro/ui/assets/fonts/`` with the running ``QApplication`` at
startup, so the QSS / DESIGN.md typography references resolve to the
exact same glyphs on every machine — independent of whether the user
has Pretendard, Noto, or only the OS default Korean font installed.

Idempotent — calling :func:`load_bundled_fonts` more than once is a
no-op (Qt deduplicates by font ID).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

_FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

_BUNDLED = (
    "NotoSansKR-Regular.ttf",
    "NotoSansKR-Medium.ttf",
    "NotoSansKR-SemiBold.ttf",
    "NotoSansKR-Bold.ttf",
)

_loaded_ids: list[int] = []


def font_paths() -> Iterable[Path]:
    return (_FONT_DIR / name for name in _BUNDLED)


def load_bundled_fonts() -> list[str]:
    """Register every bundled TTF with the live ``QFontDatabase``.

    Returns the list of family names actually loaded (for logging /
    debugging). Silently skips files that don't exist on disk so a
    stripped-down install doesn't crash.
    """
    if _loaded_ids:
        # Already registered for this process.
        return ["Noto Sans KR"]

    from PySide6.QtGui import QFontDatabase

    families: set[str] = set()
    for path in font_paths():
        if not path.exists():
            log.warning("bundled font missing: %s", path)
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            log.warning("Qt refused to load font: %s", path)
            continue
        _loaded_ids.append(font_id)
        for fam in QFontDatabase.applicationFontFamilies(font_id):
            families.add(fam)

    if families:
        log.info("loaded fonts: %s", ", ".join(sorted(families)))
    return sorted(families)
