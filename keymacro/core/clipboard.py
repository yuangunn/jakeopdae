"""Minimal cross-platform OS clipboard helper — no external dependency.

Why not pyperclip:
    - One more wheel in the PyInstaller bundle for ~50 lines of work.
    - pyperclip's Linux backend shells out to xclip / xsel — same as
      what we'd do anyway. Ditto pbcopy/pbpaste on macOS.
    - On Windows, ctypes ⇒ user32/kernel32 sidesteps subprocess
      latency and the flicker of a hidden cmd window.

Public API (both functions raise :class:`ClipboardUnavailable` if the
platform path can't run — caller decides whether to swallow or
propagate; the runner currently propagates so the step ends with a
helpful error toast):

    get_clipboard_text() -> str
    set_clipboard_text(text: str) -> None

The module level ``_BACKEND`` indirection lets tests inject a fake
backend without monkeypatching every call-site.
"""

from __future__ import annotations

import platform
import subprocess
from typing import Callable, Protocol


class ClipboardUnavailable(RuntimeError):
    """The OS clipboard couldn't be read/written. Tooling on Linux
    (xclip/xsel) might just be missing — the user gets a clear error
    message instead of a silent skip."""


class _Backend(Protocol):
    def get(self) -> str: ...
    def set(self, text: str) -> None: ...


# --- Windows backend --------------------------------------------------------


class _WindowsBackend:
    """ctypes against user32 + kernel32 — fastest path on the primary
    target platform. Handles the CF_UNICODETEXT roundtrip so Korean
    survives intact (CF_TEXT would mojibake)."""

    def get(self) -> str:
        import ctypes
        from ctypes import wintypes
        CF_UNICODETEXT = 13
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32

        if not u32.OpenClipboard(0):
            raise ClipboardUnavailable("OpenClipboard failed")
        try:
            handle = u32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = k32.GlobalLock(handle)
            if not ptr:
                raise ClipboardUnavailable("GlobalLock failed")
            try:
                return ctypes.c_wchar_p(ptr).value or ""
            finally:
                k32.GlobalUnlock(handle)
        finally:
            u32.CloseClipboard()

    def set(self, text: str) -> None:
        import ctypes
        from ctypes import wintypes
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32

        # Allocate global memory + copy the wide string in.
        nbytes = (len(text) + 1) * 2  # +1 for null terminator, *2 for wide
        h_mem = k32.GlobalAlloc(GMEM_MOVEABLE, nbytes)
        if not h_mem:
            raise ClipboardUnavailable("GlobalAlloc failed")
        ptr = k32.GlobalLock(h_mem)
        if not ptr:
            raise ClipboardUnavailable("GlobalLock failed")
        try:
            ctypes.memmove(ptr, ctypes.c_wchar_p(text), nbytes)
        finally:
            k32.GlobalUnlock(h_mem)

        if not u32.OpenClipboard(0):
            raise ClipboardUnavailable("OpenClipboard failed")
        try:
            u32.EmptyClipboard()
            if not u32.SetClipboardData(CF_UNICODETEXT, h_mem):
                raise ClipboardUnavailable("SetClipboardData failed")
            # Ownership transferred — do NOT GlobalFree the handle.
        finally:
            u32.CloseClipboard()


# --- macOS backend ----------------------------------------------------------


class _MacBackend:
    def get(self) -> str:
        try:
            return subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=2,
            ).stdout
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise ClipboardUnavailable(str(e)) from e

    def set(self, text: str) -> None:
        try:
            subprocess.run(
                ["pbcopy"], input=text, text=True, timeout=2, check=True,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired,
                subprocess.CalledProcessError) as e:
            raise ClipboardUnavailable(str(e)) from e


# --- Linux backend ----------------------------------------------------------


class _LinuxBackend:
    def _try(self, cmds: list[list[str]], **kwargs) -> subprocess.CompletedProcess:
        last: Exception | None = None
        for cmd in cmds:
            try:
                return subprocess.run(cmd, timeout=2, **kwargs)
            except FileNotFoundError as e:
                last = e
                continue
        raise ClipboardUnavailable(
            f"neither xclip nor xsel found ({last})",
        )

    def get(self) -> str:
        result = self._try(
            [["xclip", "-selection", "clipboard", "-out"],
             ["xsel", "--clipboard", "--output"]],
            capture_output=True, text=True,
        )
        return result.stdout

    def set(self, text: str) -> None:
        self._try(
            [["xclip", "-selection", "clipboard"],
             ["xsel", "--clipboard", "--input"]],
            input=text, text=True, check=True,
        )


# --- backend selection ------------------------------------------------------


def _make_default_backend() -> _Backend:
    sysname = platform.system()
    if sysname == "Windows":
        return _WindowsBackend()
    if sysname == "Darwin":
        return _MacBackend()
    return _LinuxBackend()


_BACKEND: _Backend = _make_default_backend()


def set_backend(backend: _Backend) -> None:
    """Override the auto-selected backend. Useful for tests; production
    code should never need this."""
    global _BACKEND
    _BACKEND = backend


def get_backend() -> _Backend:
    return _BACKEND


# --- public API -------------------------------------------------------------


def get_clipboard_text() -> str:
    """Return the OS clipboard's current text content, or '' if empty.

    Raises :class:`ClipboardUnavailable` if the platform path is
    unreachable (no xclip/xsel on Linux, etc.).
    """
    return _BACKEND.get()


def set_clipboard_text(text: str) -> None:
    """Write ``text`` to the OS clipboard, replacing any prior content."""
    _BACKEND.set(text)
