"""Worker thread that runs a :class:`Macro` while the GUI thread stays
responsive. The runner is wired up with a :class:`QtRunObserver` so all
progress callbacks come back as Qt signals on the main thread."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from ..core.control import RunControl
from ..core.observer import RunObserver
from ..core.runner import RunResult, Runner
from ..models.macro import Macro
from .observer_bridge import QtRunObserver

log = logging.getLogger(__name__)


class RunnerThread(QThread):
    finished_with_result = Signal(object)  # RunResult

    def __init__(
        self,
        macro: Macro,
        macro_dir: Path,
        control: RunControl,
        observer: RunObserver,
        debug_capture_dir: Optional[Path] = None,
    ) -> None:
        super().__init__()
        self._macro = macro
        self._macro_dir = macro_dir
        self._control = control
        self._observer = observer
        self._debug_capture_dir = debug_capture_dir

    def run(self) -> None:  # noqa: D401 - QThread override
        try:
            runner = Runner(
                self._macro,
                macro_dir=self._macro_dir,
                control=self._control,
                observer=self._observer,
                debug_capture_dir=self._debug_capture_dir,
            )
            result: RunResult = runner.run()
            self.finished_with_result.emit(result)
        except Exception:
            log.exception("runner thread crashed")
            self.finished_with_result.emit(
                RunResult(
                    macro_name=self._macro.name,
                    completed=False,
                    aborted_at="<crash>",
                )
            )
