"""Mouse and keyboard input simulation.

Two backends:

* :class:`PynputInput` — cross-platform, uses ``pynput`` underneath. Suitable
  for browsers, office apps, and most desktop software.
* :class:`SendInputWindows` — Windows-only, talks to ``user32!SendInput``
  directly. Some emulators / games ignore pynput-driven events because they
  are not perceived as hardware input; SendInput goes one layer deeper.

The :class:`Input` Protocol is what callers depend on, so tests can swap in
a fake.
"""

from __future__ import annotations

import sys
import time
from typing import Literal, Protocol, runtime_checkable

InputMode = Literal["normal", "raw"]
Button = Literal["left", "right", "middle"]


@runtime_checkable
class Input(Protocol):
    def click(self, x: int, y: int, button: Button = "left", double: bool = False) -> None: ...
    def key(self, keys: str) -> None: ...
    def type_text(self, text: str, interval_s: float = 0.0) -> None: ...
    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_s: float = 0.3,
        button: Button = "left",
    ) -> None: ...


# --- pynput-backed implementation -------------------------------------------------


_MODIFIER_MAP = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "win": "cmd",
    "cmd": "cmd",
    "super": "cmd",
    "meta": "cmd",
}

_SPECIAL_KEY_MAP = {
    "enter": "enter",
    "return": "enter",
    "tab": "tab",
    "esc": "esc",
    "escape": "esc",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "insert": "insert",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "pageup": "page_up",
    "pagedown": "page_down",
    "capslock": "caps_lock",
    "f1": "f1",
    "f2": "f2",
    "f3": "f3",
    "f4": "f4",
    "f5": "f5",
    "f6": "f6",
    "f7": "f7",
    "f8": "f8",
    "f9": "f9",
    "f10": "f10",
    "f11": "f11",
    "f12": "f12",
}


class PynputInput:
    """Cross-platform input simulation. Constructed lazily so test envs without
    a display server can still import this module."""

    def __init__(self) -> None:
        from pynput.keyboard import Controller as KeyCtl, Key, KeyCode  # type: ignore[import-not-found]
        from pynput.mouse import Button as MouseButton, Controller as MouseCtl  # type: ignore[import-not-found]

        self._mouse = MouseCtl()
        self._keyboard = KeyCtl()
        self._MouseButton = MouseButton
        self._Key = Key
        self._KeyCode = KeyCode

    def _btn(self, name: Button):
        return {
            "left": self._MouseButton.left,
            "right": self._MouseButton.right,
            "middle": self._MouseButton.middle,
        }[name]

    def click(self, x: int, y: int, button: Button = "left", double: bool = False) -> None:
        self._mouse.position = (int(x), int(y))
        self._mouse.click(self._btn(button), 2 if double else 1)

    def _resolve_key(self, name: str):
        norm = name.strip().lower()
        if not norm:
            raise ValueError("empty key token")
        if norm in _SPECIAL_KEY_MAP:
            return getattr(self._Key, _SPECIAL_KEY_MAP[norm])
        if norm in _MODIFIER_MAP:
            return getattr(self._Key, _MODIFIER_MAP[norm])
        if len(norm) == 1:
            return self._KeyCode.from_char(norm)
        if hasattr(self._Key, norm):
            return getattr(self._Key, norm)
        raise ValueError(f"unknown key token: {name!r}")

    def key(self, keys: str) -> None:
        parts = [p for p in (s.strip() for s in keys.split("+")) if p]
        if not parts:
            raise ValueError("empty key combo")
        resolved = [self._resolve_key(p) for p in parts]
        modifiers, main = resolved[:-1], resolved[-1]
        for m in modifiers:
            self._keyboard.press(m)
        try:
            self._keyboard.press(main)
            self._keyboard.release(main)
        finally:
            for m in reversed(modifiers):
                self._keyboard.release(m)

    def type_text(self, text: str, interval_s: float = 0.0) -> None:
        if interval_s <= 0:
            self._keyboard.type(text)
            return
        for ch in text:
            self._keyboard.type(ch)
            time.sleep(interval_s)

    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_s: float = 0.3,
        button: Button = "left",
    ) -> None:
        b = self._btn(button)
        self._mouse.position = (int(x1), int(y1))
        self._mouse.press(b)
        try:
            steps = max(1, int(duration_s * 60))
            for i in range(1, steps + 1):
                t = i / steps
                self._mouse.position = (
                    int(x1 + (x2 - x1) * t),
                    int(y1 + (y2 - y1) * t),
                )
                if duration_s > 0:
                    time.sleep(duration_s / steps)
        finally:
            self._mouse.release(b)


# --- Windows SendInput backend ----------------------------------------------------


class SendInputWindows:
    """Raw mouse input via ``user32!SendInput``.

    Use this for applications that filter out pynput-style synthesized events
    (some games and emulators). Keyboard input is delegated to
    :class:`PynputInput` because translating arbitrary key combos to virtual
    key codes is more involved than this lightweight backend needs to be —
    raw mouse alone covers the most common use case (clicks inside an
    emulator window).
    """

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("SendInputWindows is Windows-only")

        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._build_structs()
        # For keys / typing, fall back to pynput.
        self._fallback = PynputInput()

    # --- ctypes plumbing --------------------------------------------------------

    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1

    def _build_structs(self) -> None:
        ctypes = self._ctypes
        wintypes = self._wintypes

        # ULONG_PTR is 32 or 64 bits depending on the platform.
        ULONG_PTR = (
            ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
        )

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self._INPUT = INPUT
        self._MOUSEINPUT = MOUSEINPUT

    # --- helpers ----------------------------------------------------------------

    def _send(self, inputs: list) -> None:
        n = len(inputs)
        arr = (self._INPUT * n)(*inputs)
        sent = self._user32.SendInput(n, arr, self._ctypes.sizeof(self._INPUT))
        if sent != n:
            raise OSError(self._ctypes.get_last_error(), "SendInput failed")

    def _abs_move(self, x: int, y: int):
        screen_w = max(1, self._user32.GetSystemMetrics(self.SM_CXSCREEN))
        screen_h = max(1, self._user32.GetSystemMetrics(self.SM_CYSCREEN))
        nx = int(x * 65535 / max(1, screen_w - 1))
        ny = int(y * 65535 / max(1, screen_h - 1))
        mi = self._MOUSEINPUT(
            dx=nx,
            dy=ny,
            mouseData=0,
            dwFlags=self.MOUSEEVENTF_MOVE | self.MOUSEEVENTF_ABSOLUTE,
            time=0,
            dwExtraInfo=0,
        )
        return self._INPUT(type=self.INPUT_MOUSE, mi=mi)

    def _btn_flags(self, name: Button) -> tuple[int, int]:
        return {
            "left": (self.MOUSEEVENTF_LEFTDOWN, self.MOUSEEVENTF_LEFTUP),
            "right": (self.MOUSEEVENTF_RIGHTDOWN, self.MOUSEEVENTF_RIGHTUP),
            "middle": (self.MOUSEEVENTF_MIDDLEDOWN, self.MOUSEEVENTF_MIDDLEUP),
        }[name]

    def _btn_event(self, flag: int):
        return self._INPUT(
            type=self.INPUT_MOUSE,
            mi=self._MOUSEINPUT(0, 0, 0, flag, 0, 0),
        )

    # --- API --------------------------------------------------------------------

    def click(self, x: int, y: int, button: Button = "left", double: bool = False) -> None:
        down, up = self._btn_flags(button)
        events = [self._abs_move(x, y)]
        repetitions = 2 if double else 1
        for _ in range(repetitions):
            events.append(self._btn_event(down))
            events.append(self._btn_event(up))
        self._send(events)

    def key(self, keys: str) -> None:
        # Delegated; arbitrary key combos via SendInput are out of scope for v0.
        self._fallback.key(keys)

    def type_text(self, text: str, interval_s: float = 0.0) -> None:
        self._fallback.type_text(text, interval_s)

    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_s: float = 0.3,
        button: Button = "left",
    ) -> None:
        down, up = self._btn_flags(button)
        self._send([self._abs_move(x1, y1), self._btn_event(down)])
        try:
            steps = max(1, int(duration_s * 60))
            for i in range(1, steps + 1):
                t = i / steps
                mx = int(x1 + (x2 - x1) * t)
                my = int(y1 + (y2 - y1) * t)
                self._send([self._abs_move(mx, my)])
                if duration_s > 0:
                    time.sleep(duration_s / steps)
        finally:
            self._send([self._btn_event(up)])


# --- factory ----------------------------------------------------------------------


def make_input(mode: InputMode = "normal") -> Input:
    """Construct an :class:`Input` backend.

    ``mode='raw'`` requests the lower-level Windows backend; on non-Windows
    platforms it silently falls back to pynput.
    """
    if mode == "raw" and sys.platform == "win32":
        return SendInputWindows()
    return PynputInput()
