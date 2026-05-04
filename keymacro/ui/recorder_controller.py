"""Bridge between :class:`Recorder` (runs in pynput threads) and Qt.

Pynput callbacks fire on listener threads, so the F8-stop signal can't
touch widgets directly. This controller exposes a Qt :class:`Signal`
that the GUI thread can hook into safely.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal

from ..core.recorder import RecordedEvent, Recorder

log = logging.getLogger(__name__)


class RecorderController(QObject):
    """Wraps :class:`Recorder` and re-emits its callbacks as Qt signals."""

    started = Signal()
    stopped_externally = Signal()
    """Fired when the user pressed the stop key (F8). The GUI then calls
    :meth:`stop` to harvest events and collapse the recorder state."""

    event_recorded = Signal(object)
    """RecordedEvent — useful for live UI feedback (e.g. count in status bar)."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._recorder: Optional[Recorder] = None

    @property
    def is_running(self) -> bool:
        return self._recorder is not None and self._recorder.is_running

    def start(self) -> None:
        if self.is_running:
            return
        self._recorder = Recorder(
            stop_key="f8",
            on_event=self.event_recorded.emit,
            on_stop=self.stopped_externally.emit,
        )
        self._recorder.start()
        self.started.emit()
        log.info("recorder controller started")

    def stop(self) -> list[RecordedEvent]:
        if self._recorder is None:
            return []
        events = self._recorder.stop()
        self._recorder = None
        log.info("recorder controller stopped — %d events", len(events))
        return events
