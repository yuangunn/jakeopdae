"""Global hotkey listener.

Wraps :class:`pynput.keyboard.GlobalHotKeys` so the rest of the codebase
does not depend on pynput directly. Defaults: F9 = start, F10 = stop,
F11 = pause/resume.

Hotkey strings use the pynput ``GlobalHotKeys`` syntax: angle-brackets for
named keys (``<f9>``), ``+`` to combine modifiers (``<ctrl>+<shift>+r``).
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

log = logging.getLogger(__name__)


class HotkeyManager:
    """Bind start/stop/pause callbacks to global hotkeys."""

    DEFAULT_BINDINGS: dict[str, str] = {
        "start": "<f9>",
        "stop": "<f10>",
        "pause": "<f11>",
    }

    def __init__(
        self,
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_pause: Optional[Callable[[], None]] = None,
        bindings: Optional[dict[str, str]] = None,
    ) -> None:
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_pause = on_pause
        self._bindings = {**self.DEFAULT_BINDINGS, **(bindings or {})}
        self._listener = None  # type: ignore[var-annotated]

    @property
    def bindings(self) -> dict[str, str]:
        return dict(self._bindings)

    def start(self) -> None:
        """Begin listening. Idempotent — calling twice is a no-op."""
        if self._listener is not None:
            return

        from pynput.keyboard import GlobalHotKeys  # type: ignore[import-not-found]

        mapping: dict[str, Callable[[], None]] = {}
        if self._on_start:
            mapping[self._bindings["start"]] = self._safe(self._on_start)
        if self._on_stop:
            mapping[self._bindings["stop"]] = self._safe(self._on_stop)
        if self._on_pause:
            mapping[self._bindings["pause"]] = self._safe(self._on_pause)

        if not mapping:
            raise ValueError("HotkeyManager needs at least one callback")

        self._listener = GlobalHotKeys(mapping)
        self._listener.start()
        log.info("hotkey listener started: %s", mapping.keys())

    def stop(self) -> None:
        if self._listener is None:
            return
        try:
            self._listener.stop()
        except Exception:
            log.exception("hotkey listener.stop() raised")
        self._listener = None
        log.info("hotkey listener stopped")

    def __enter__(self) -> "HotkeyManager":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()

    @staticmethod
    def _safe(fn: Callable[[], None]) -> Callable[[], None]:
        def _wrapped() -> None:
            try:
                fn()
            except Exception:
                log.exception("hotkey callback raised")

        return _wrapped
