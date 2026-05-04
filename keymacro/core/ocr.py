"""Tesseract-backed OCR for screen-region text extraction.

Optional dependency: ``pytesseract`` (Python bindings) plus the
Tesseract binary installed on the OS — on Windows the standard install
path is ``C:\\Program Files\\Tesseract-OCR\\tesseract.exe`` and we
auto-detect it here so the user doesn't have to set ``TESSDATA_PREFIX``.

Korean recognition needs the ``kor`` language pack, included with the
Windows installer when the user ticks "Korean" during setup.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


# Cached so we don't re-scan PATH / well-known dirs on every poll.
_tesseract_resolved = False


class TesseractMissing(RuntimeError):
    """Raised when pytesseract or the Tesseract binary aren't available.

    The message is Korean-friendly so it surfaces nicely in the GUI's
    failure dialog without further translation.
    """


def _resolve_tesseract_cmd() -> Optional[str]:
    """Tell pytesseract where the Tesseract binary lives, if we can find it.

    pytesseract assumes ``tesseract`` is on ``PATH`` by default; on a
    fresh Windows install it usually isn't. We probe the standard
    locations and set ``pytesseract.pytesseract.tesseract_cmd`` so the
    user doesn't have to fiddle with environment variables.
    """
    global _tesseract_resolved
    if _tesseract_resolved:
        return None
    _tesseract_resolved = True

    try:
        import pytesseract  # type: ignore[import-not-found]
    except ImportError:
        return None

    if sys.platform != "win32":
        return None

    candidates = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    )
    for c in candidates:
        if os.path.exists(c):
            pytesseract.pytesseract.tesseract_cmd = c
            log.info("Tesseract resolved at %s", c)
            return c
    return None


def read_text(image_bgr: np.ndarray, language: str = "kor+eng") -> str:
    """Run OCR on a BGR numpy image and return the recognised text.

    Raises :class:`TesseractMissing` if pytesseract or the Tesseract
    binary can't be found — caller should turn that into a friendly
    Korean install hint.
    """
    try:
        import pytesseract  # type: ignore[import-not-found]
    except ImportError as e:
        raise TesseractMissing(
            "pytesseract이 설치되어 있지 않아요.\n"
            "  pip install 'keymacro[ocr]'\n"
            "그리고 Tesseract 본체도 설치해 주세요:\n"
            "  https://github.com/UB-Mannheim/tesseract/wiki\n"
            "(설치 시 Korean 언어팩 체크)"
        ) from e

    _resolve_tesseract_cmd()

    import cv2

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    try:
        return pytesseract.image_to_string(rgb, lang=language)
    except pytesseract.TesseractNotFoundError as e:
        raise TesseractMissing(
            "Tesseract 본체를 찾을 수 없어요.\n"
            "Windows: https://github.com/UB-Mannheim/tesseract/wiki 에서 다운로드 후 설치 (Korean 언어팩 포함).\n"
            "설치 후 Chrome / 시스템 재시작이 필요할 수도 있습니다."
        ) from e


def text_matches(
    haystack: str, needle: str, mode: str = "contains", case_sensitive: bool = False,
) -> bool:
    """Common matching helper for OCR triggers."""
    if not case_sensitive:
        haystack = haystack.lower()
        needle = needle.lower()
    if mode == "exact":
        return haystack.strip() == needle.strip()
    if mode == "regex":
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            return bool(re.search(needle, haystack, flags=flags))
        except re.error:
            log.warning("invalid regex %r", needle)
            return False
    return needle in haystack
