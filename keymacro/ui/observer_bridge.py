"""Bridge a :class:`RunObserver` running on a worker thread to Qt signals.

The runner emits observer callbacks from whatever thread it is running on
(typically a :class:`QThread`). Qt widgets must only be touched from the
GUI thread, so we re-emit each callback as a signal — the Qt event loop
takes care of marshalling it back to the main thread.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal

from ..core.matcher import MatchResult


class QtRunObserver(QObject):
    run_started = Signal(str)
    step_started = Signal(str, int, int)          # step_id, attempt, iteration
    match_attempt = Signal(str, float, bool)      # step_id, score, found
    step_ended = Signal(str, bool, str)           # step_id, success, error
    failure_capture = Signal(str, object)         # step_id, np.ndarray
    run_ended = Signal(bool, str)                 # completed, aborted_at

    # --- RunObserver protocol -------------------------------------------------

    def on_run_start(self, macro_name: str) -> None:
        self.run_started.emit(macro_name)

    def on_step_start(self, step_id: str, attempt: int, iteration: int) -> None:
        self.step_started.emit(step_id, attempt, iteration)

    def on_match_attempt(self, step_id: str, score: float, found: bool) -> None:
        self.match_attempt.emit(step_id, score, found)

    def on_step_end(
        self,
        step_id: str,
        success: bool,
        match: Optional[MatchResult],
        error: Optional[str],
    ) -> None:
        self.step_ended.emit(step_id, success, error or "")

    def on_failure_capture(self, step_id: str, image: np.ndarray) -> None:
        self.failure_capture.emit(step_id, image)

    def on_run_end(self, completed: bool, aborted_at: Optional[str]) -> None:
        self.run_ended.emit(completed, aborted_at or "")
