"""Runner observation protocol.

Anything that wants to react to runner progress (a GUI debugger, the CLI
status line, a tray-icon badge, a Telegram notifier) implements this
protocol. The runner calls these methods inside its execution loop, so
implementations must be quick and non-blocking.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

import numpy as np

from .matcher import MatchResult


@runtime_checkable
class RunObserver(Protocol):
    def on_run_start(self, macro_name: str) -> None: ...
    def on_step_start(self, step_id: str, attempt: int, iteration: int) -> None: ...
    def on_match_attempt(
        self, step_id: str, score: float, found: bool
    ) -> None: ...
    def on_step_end(
        self,
        step_id: str,
        success: bool,
        match: Optional[MatchResult],
        error: Optional[str],
    ) -> None: ...
    def on_failure_capture(self, step_id: str, image: np.ndarray) -> None: ...
    def on_run_end(self, completed: bool, aborted_at: Optional[str]) -> None: ...


class _NullObserver:
    """No-op observer; used when none is supplied."""

    def on_run_start(self, macro_name: str) -> None: ...
    def on_step_start(self, step_id: str, attempt: int, iteration: int) -> None: ...
    def on_match_attempt(self, step_id: str, score: float, found: bool) -> None: ...
    def on_step_end(self, step_id, success, match, error) -> None: ...  # type: ignore[no-untyped-def]
    def on_failure_capture(self, step_id: str, image: np.ndarray) -> None: ...
    def on_run_end(self, completed: bool, aborted_at: Optional[str]) -> None: ...


def null_observer() -> RunObserver:
    return _NullObserver()


class MultiObserver:
    """Fan-out helper — forward every callback to a list of observers.

    Used by the GUI to combine its Qt-bridge observer with the history
    store's persistence observer so a single ``Runner.run()`` updates
    both the live UI and the SQLite log.
    """

    def __init__(self, *observers: RunObserver) -> None:
        self._observers = observers

    def _forward(self, name: str, *args, **kwargs) -> None:
        for o in self._observers:
            try:
                getattr(o, name)(*args, **kwargs)
            except Exception:  # pragma: no cover — observer must never break the run
                import logging
                logging.getLogger(__name__).exception(
                    "observer %r raised in %s", o, name,
                )

    def on_run_start(self, macro_name: str) -> None:
        self._forward("on_run_start", macro_name)

    def on_step_start(self, step_id: str, attempt: int, iteration: int) -> None:
        self._forward("on_step_start", step_id, attempt, iteration)

    def on_match_attempt(self, step_id: str, score: float, found: bool) -> None:
        self._forward("on_match_attempt", step_id, score, found)

    def on_step_end(self, step_id, success, match, error) -> None:  # type: ignore[no-untyped-def]
        self._forward("on_step_end", step_id, success, match, error)

    def on_failure_capture(self, step_id, image) -> None:  # type: ignore[no-untyped-def]
        self._forward("on_failure_capture", step_id, image)

    def on_run_end(self, completed: bool, aborted_at) -> None:  # type: ignore[no-untyped-def]
        self._forward("on_run_end", completed, aborted_at)
