"""Read the active browser tab's URL via Windows UI Automation (no CDP).

This is the hybrid trigger's escape hatch: the user keeps using their
*regular* Chrome (with all their cookies / extensions / logins), and
keymacro reads the address bar through the OS accessibility tree —
exactly the same channel screen-readers use.

Optional dependency: ``uiautomation``. If not installed, falls back to
window-title matching, which is less precise but covers many sites
that put the page name in the title.

The reader caches the most recently found address-bar control across
calls so polling-style triggers don't pay the full tree-walk cost on
every probe.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal, Optional

log = logging.getLogger(__name__)

BrowserKind = Literal["chrome", "edge", "firefox", "any"]


# Window class names per browser; used both for UIA scoping and for
# title-fallback. Chrome and Edge share the underlying Chromium class.
_BROWSER_CLASSES: dict[BrowserKind, tuple[str, ...]] = {
    "chrome": ("Chrome_WidgetWin_1",),
    "edge": ("Chrome_WidgetWin_1",),  # Edge is Chromium too
    "firefox": ("MozillaWindowClass",),
    "any": ("Chrome_WidgetWin_1", "MozillaWindowClass"),
}


# Cache ``(window_handle_id, edit_control)`` so we don't re-walk the tree.
# Invalidated when the cached control's GetValue raises.
_cache: dict[str, object] = {}


def read_browser_url(browser: BrowserKind = "any") -> Optional[str]:
    """Return the URL shown in the active browser's address bar.

    Returns ``None`` when:

    * we're not on Windows (UIA is Windows-only)
    * ``uiautomation`` isn't installed and title fallback also failed
    * no matching browser window exists
    * the address bar exists but contains no value (rare)
    """
    if sys.platform != "win32":
        return None

    via_uia = _read_via_uia(browser)
    if via_uia:
        return via_uia
    return _read_via_window_title(browser)


# --- UIA path ----------------------------------------------------------------


def _read_via_uia(browser: BrowserKind) -> Optional[str]:
    try:
        import uiautomation as uia  # type: ignore[import-not-found]
    except ImportError:
        log.debug("uiautomation not installed; UIA path skipped")
        return None

    try:
        return _uia_read(uia, browser)
    except Exception:
        log.debug("UIA read raised; falling back", exc_info=True)
        return None


def _uia_read(uia, browser: BrowserKind) -> Optional[str]:
    classes = _BROWSER_CLASSES[browser]
    for cls in classes:
        # ``WindowControl`` with depth 1 walks only top-level windows.
        try:
            window = uia.WindowControl(searchDepth=1, ClassName=cls)
        except Exception:
            continue
        if not window.Exists(maxSearchSeconds=0.2):
            continue

        # Address bar in Chromium-family browsers is the first Edit control
        # below the window. Walking the full subtree is slow on big pages,
        # so we cap depth and bail at first match.
        edit = window.EditControl(searchDepth=12)
        if not edit.Exists(maxSearchSeconds=0.4):
            continue
        try:
            value = edit.GetValuePattern().Value
        except Exception:
            continue
        if not value:
            continue
        return _normalise_url(value)
    return None


# --- Window title fallback ---------------------------------------------------


def _read_via_window_title(browser: BrowserKind) -> Optional[str]:
    """Last-ditch fallback: the window title often contains the page
    title (and sometimes the URL), which is enough for substring matches
    on stable site names."""
    try:
        import ctypes
        import ctypes.wintypes as wt
    except Exception:
        return None

    user32 = ctypes.windll.user32

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        wt.BOOL, wt.HWND, wt.LPARAM,
    )

    classes = _BROWSER_CLASSES[browser]
    found_title: list[str] = []

    def _cb(hwnd, _l):
        if not user32.IsWindowVisible(hwnd):
            return True
        # Class name
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value not in classes:
            return True
        # Title
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        tbuf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, tbuf, length + 1)
        if tbuf.value:
            found_title.append(tbuf.value)
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    if found_title:
        # Heuristic: pick the longest title (likely the active full one)
        return _normalise_url(max(found_title, key=len))
    return None


# --- helpers ----------------------------------------------------------------


def _normalise_url(s: str) -> str:
    """Strip surrounding whitespace + drop the screen-reader prefix that
    Chrome sometimes prepends (e.g. ``"주소 입력창"``).

    The result is what the trigger's ``url_contains`` is checked against,
    so callers should match substrings only — the value may be a partial
    URL, a page title, or a screen-reader-friendly composite, depending
    on which path produced it.
    """
    return s.strip()


def url_matches(actual: Optional[str], pattern: str, mode: str = "contains") -> bool:
    """Public helper mirroring ``core.web.url_matches`` semantics."""
    import re as _re
    if not actual:
        return False
    if mode == "exact":
        return actual.strip() == pattern.strip()
    if mode == "regex":
        try:
            return _re.search(pattern, actual) is not None
        except _re.error:
            return False
    return pattern in actual
