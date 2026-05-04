"""Thread-safe stop + pause control shared between the runner and any
external trigger source (hotkey listener, GUI buttons, system-tray menu)."""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable


@runtime_checkable
class Control(Protocol):
    def is_stopped(self) -> bool: ...
    def is_paused(self) -> bool: ...


class RunControl:
    """Default :class:`Control` implementation backed by ``threading.Event``."""

    def __init__(self) -> None:
        self._stopped = threading.Event()
        self._paused = threading.Event()

    # --- stop -----------------------------------------------------------------

    def stop(self) -> None:
        self._stopped.set()

    def is_stopped(self) -> bool:
        return self._stopped.is_set()

    # --- pause ----------------------------------------------------------------

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def toggle_pause(self) -> bool:
        """Flip the pause state. Returns the new state (``True`` = paused)."""
        if self._paused.is_set():
            self._paused.clear()
            return False
        self._paused.set()
        return True

    def is_paused(self) -> bool:
        return self._paused.is_set()

    # --- lifecycle ------------------------------------------------------------

    def reset(self) -> None:
        self._stopped.clear()
        self._paused.clear()

    # Compatibility with the older StopFlag Protocol (``is_set()``) so callers
    # that only need stop semantics can pass a RunControl in either slot.
    def is_set(self) -> bool:
        return self._stopped.is_set()
