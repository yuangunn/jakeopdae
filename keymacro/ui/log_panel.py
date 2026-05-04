"""A QTextEdit-backed log handler.

Routes the standard ``logging`` records into a read-only text widget so
the GUI can show them without competing with the terminal output.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGroupBox, QPushButton, QTextEdit, QVBoxLayout


class _LogBridge(QObject):
    record = Signal(str)


class LogPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Log")
        layout = QVBoxLayout(self)
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        layout.addWidget(self.view)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.view.clear)
        layout.addWidget(clear_btn)

        self._bridge = _LogBridge()
        self._bridge.record.connect(self.view.append)

        self._handler = _GuiHandler(self._bridge)
        self._handler.setLevel(logging.INFO)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                              datefmt="%H:%M:%S")
        )

    def attach(self) -> None:
        logging.getLogger().addHandler(self._handler)

    def detach(self) -> None:
        logging.getLogger().removeHandler(self._handler)


class _GuiHandler(logging.Handler):
    def __init__(self, bridge: _LogBridge) -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._bridge.record.emit(msg)
        except Exception:
            self.handleError(record)
