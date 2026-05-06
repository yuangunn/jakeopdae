"""Win32 window manipulation — find, resize, move, maximize.

Pure ``ctypes`` wrapper around ``user32`` so we don't pull in pywin32
(saves ~3 MB in the PyInstaller bundle for what we need). Windows
only; ``find_*`` calls return ``None`` and ``set_*`` calls no-op on
non-Windows so the module imports cleanly during cross-platform tests.

Coordinate system: virtual desktop. The primary monitor's top-left
corner is ``(0, 0)``; secondaries can sit at positive or negative x/y
depending on Windows display layout. ``SetWindowPos`` accepts those
coordinates directly, so a window can be placed on any monitor (or
straddle two) without per-monitor logic.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WindowInfo:
    """Snapshot of an OS window. ``hwnd`` is opaque on non-Windows."""

    hwnd: int
    title: str
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class MonitorInfo:
    """A single monitor's geometry. ``work_*`` excludes the taskbar."""

    index: int
    primary: bool
    x: int
    y: int
    w: int
    h: int
    work_x: int
    work_y: int
    work_w: int
    work_h: int


# ---------------------------------------------------------------------------
# Windows-only path
# ---------------------------------------------------------------------------

_IS_WINDOWS = sys.platform == "win32"


if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    # ShowWindow commands
    SW_HIDE = 0
    SW_NORMAL = 1
    SW_MINIMIZE = 6
    SW_MAXIMIZE = 3
    SW_RESTORE = 9
    SW_SHOW = 5

    # SetWindowPos flags
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    HWND_TOP = 0
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", _RECT),
            ("rcWork", _RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    _MONITORINFOF_PRIMARY = 0x1

    # WNDENUMPROC: BOOL CALLBACK(HWND, LPARAM) — Windows defines LPARAM
    # as signed pointer-sized integer, so we use c_void_p in Python and
    # let ctypes do the right thing.
    _EnumWindowsProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, ctypes.c_void_p,
    )
    _MonitorEnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(_RECT),
        ctypes.c_void_p,
    )

    _user32.EnumWindows.argtypes = [_EnumWindowsProc, ctypes.c_void_p]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.GetWindowTextW.argtypes = [
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int,
    ]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetForegroundWindow.argtypes = []
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowRect.argtypes = [
        wintypes.HWND, ctypes.POINTER(_RECT),
    ]
    _user32.GetWindowRect.restype = wintypes.BOOL
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.EnumDisplayMonitors.argtypes = [
        wintypes.HDC, ctypes.POINTER(_RECT),
        _MonitorEnumProc, ctypes.c_void_p,
    ]
    _user32.EnumDisplayMonitors.restype = wintypes.BOOL
    _user32.GetMonitorInfoW.argtypes = [
        wintypes.HMONITOR, ctypes.POINTER(_MONITORINFO),
    ]
    _user32.GetMonitorInfoW.restype = wintypes.BOOL


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_supported() -> bool:
    return _IS_WINDOWS


def _get_window_info(hwnd: int) -> Optional[WindowInfo]:
    if not _IS_WINDOWS:
        return None
    length = _user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    rect = _RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return WindowInfo(
        hwnd=int(hwnd),
        title=buf.value,
        x=rect.left, y=rect.top,
        w=rect.right - rect.left,
        h=rect.bottom - rect.top,
    )


def list_visible_windows() -> list[WindowInfo]:
    """Every visible top-level window with a non-empty title."""
    if not _IS_WINDOWS:
        return []
    out: list[WindowInfo] = []

    def _cb(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        info = _get_window_info(hwnd)
        if info is None or not info.title.strip():
            return True
        out.append(info)
        return True

    _user32.EnumWindows(_EnumWindowsProc(_cb), 0)
    return out


def find_window_by_title(substring: str) -> Optional[WindowInfo]:
    """First visible window whose title contains ``substring`` (case-insensitive).

    Walks the Z-order via ``EnumWindows``, so the topmost matching
    window wins when there are duplicates."""
    if not _IS_WINDOWS or not substring.strip():
        return None
    needle = substring.casefold()
    for info in list_visible_windows():
        if needle in info.title.casefold():
            return info
    return None


def get_foreground_window() -> Optional[WindowInfo]:
    """Whichever window currently has OS focus (None if desktop / no
    foreground window)."""
    if not _IS_WINDOWS:
        return None
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    return _get_window_info(hwnd)


def list_monitors() -> list[MonitorInfo]:
    """Every connected monitor in the order Windows reports them.

    ``MonitorInfo.index`` is just the position in this list — useful
    for "monitor 0 / 1 / 2" presets in the UI. Primary monitor is
    flagged via ``primary=True`` (not necessarily index 0)."""
    if not _IS_WINDOWS:
        return []
    out: list[MonitorInfo] = []

    def _cb(hmonitor, _hdc, _rect, _lparam):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not _user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return True
        out.append(MonitorInfo(
            index=len(out),
            primary=bool(info.dwFlags & _MONITORINFOF_PRIMARY),
            x=info.rcMonitor.left, y=info.rcMonitor.top,
            w=info.rcMonitor.right - info.rcMonitor.left,
            h=info.rcMonitor.bottom - info.rcMonitor.top,
            work_x=info.rcWork.left, work_y=info.rcWork.top,
            work_w=info.rcWork.right - info.rcWork.left,
            work_h=info.rcWork.bottom - info.rcWork.top,
        ))
        return True

    _user32.EnumDisplayMonitors(None, None, _MonitorEnumProc(_cb), 0)
    return out


def set_window_bounds(hwnd: int, x: int, y: int, w: int, h: int) -> bool:
    """Move + resize a window. Coordinates are virtual-desktop space
    (negative values land on monitors left/above the primary). ``True``
    on success."""
    if not _IS_WINDOWS:
        return False
    flags = SWP_NOZORDER  # don't disturb z-order; user expects the
                          # macro to pop the window forward separately
    # Restore first so a maximized window can actually move.
    _user32.ShowWindow(hwnd, SW_RESTORE)
    return bool(_user32.SetWindowPos(hwnd, 0, x, y, w, h, flags))


def maximize_window(hwnd: int) -> bool:
    if not _IS_WINDOWS:
        return False
    return bool(_user32.ShowWindow(hwnd, SW_MAXIMIZE))


def minimize_window(hwnd: int) -> bool:
    if not _IS_WINDOWS:
        return False
    return bool(_user32.ShowWindow(hwnd, SW_MINIMIZE))


def restore_window(hwnd: int) -> bool:
    if not _IS_WINDOWS:
        return False
    return bool(_user32.ShowWindow(hwnd, SW_RESTORE))


def bring_to_foreground(hwnd: int) -> bool:
    if not _IS_WINDOWS:
        return False
    return bool(_user32.SetForegroundWindow(hwnd))


def fullscreen_on_monitor(hwnd: int, monitor_index: int) -> bool:
    """Place a window covering an entire monitor (work area, so the
    taskbar still shows). ``monitor_index`` clamps to the available
    list — out-of-range falls back to the primary."""
    if not _IS_WINDOWS:
        return False
    monitors = list_monitors()
    if not monitors:
        return False
    if 0 <= monitor_index < len(monitors):
        m = monitors[monitor_index]
    else:
        # Out of range → primary
        m = next((mm for mm in monitors if mm.primary), monitors[0])
    return set_window_bounds(
        hwnd, m.work_x, m.work_y, m.work_w, m.work_h,
    )
