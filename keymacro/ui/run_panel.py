"""Start/Stop/Pause buttons + status indicator + live match score."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class RunPanel(QGroupBox):
    start_requested = Signal()
    stop_requested = Signal()
    pause_requested = Signal()

    def __init__(self) -> None:
        super().__init__("Run")
        outer = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start (F9)")
        self.stop_btn = QPushButton("Stop (F10)")
        self.pause_btn = QPushButton("Pause/Resume (F11)")
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.pause_btn)
        outer.addLayout(btn_row)

        self.status = QLabel("idle")
        outer.addWidget(self.status)

        # Live match-score gauge for Phase 5 debugging.
        self.match_label = QLabel("match: —")
        self.match_bar = QProgressBar()
        self.match_bar.setRange(0, 100)
        self.match_bar.setValue(0)
        outer.addWidget(self.match_label)
        outer.addWidget(self.match_bar)

        self.start_btn.clicked.connect(self.start_requested)
        self.stop_btn.clicked.connect(self.stop_requested)
        self.pause_btn.clicked.connect(self.pause_requested)

        self.set_running(False)

    # --- public API -----------------------------------------------------

    def set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.pause_btn.setEnabled(running)
        self.status.setText("running" if running else "idle")

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    def set_match_score(self, step_id: str, score: float, found: bool) -> None:
        pct = max(0, min(100, int(score * 100)))
        self.match_bar.setValue(pct)
        marker = "OK" if found else "··"
        self.match_label.setText(f"match: [{marker}] {step_id} score={score:.3f}")
