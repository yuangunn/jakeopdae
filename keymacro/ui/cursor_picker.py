"""5-second countdown that captures the global cursor position.

Same UX pattern as ``WindowPickerDialog`` — show a countdown, refresh
a live preview every half second so the user knows exactly what
they'll get, then emit the captured ``(x, y)`` when the timer
expires. Uses ``QCursor.pos()`` for cross-platform support (returns
global desktop coordinates that match what ``ClickAction`` expects).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import C


class CursorPickerDialog(QDialog):
    picked = Signal(int, int)
    """``(x, y)`` global desktop coordinates of the cursor at capture time."""

    def __init__(self, parent: Optional[QWidget] = None, countdown_s: int = 5) -> None:
        super().__init__(parent)
        self.setWindowTitle("마우스 위치 잡기")
        self.setModal(False)
        self.setMinimumWidth(360)
        self._remaining = max(1, int(countdown_s))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(10)

        title = QLabel("🎯 마우스 위치 잡기")
        title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', sans-serif;"
            f"font-size: 18px; font-weight: 600; color: {C['on-surface']};"
        )
        outer.addWidget(title)

        instructions = QLabel(
            "원하는 위치로 마우스 커서를 옮긴 채 카운트다운이 끝나길\n"
            "기다려 주세요. 화면 어디든 OK — 다른 모니터도 됩니다."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            f"color: {C['on-surface-variant']}; font-size: 12px;"
        )
        outer.addWidget(instructions)

        self._countdown_lbl = QLabel(f"{self._remaining}")
        self._countdown_lbl.setAlignment(Qt.AlignCenter)
        self._countdown_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
            f"font-size: 36px; font-weight: 700;"
            f"color: {C['primary']}; padding: 12px;"
        )
        outer.addWidget(self._countdown_lbl)

        self._preview_lbl = QLabel("(위치 감지 중…)")
        self._preview_lbl.setAlignment(Qt.AlignCenter)
        self._preview_lbl.setStyleSheet(
            f"color: {C['on-surface']}; font-size: 13px;"
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
            f"background-color: {C['surface-container-low']};"
            f"border: 1px solid {C['outline-variant']};"
            f"border-radius: 6px; padding: 10px 12px;"
        )
        outer.addWidget(self._preview_lbl)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("취소")
        cancel.setProperty("role", "ghost")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        outer.addLayout(footer)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._half_seconds_left = self._remaining * 2

    def _tick(self) -> None:
        pos = QCursor.pos()
        self._preview_lbl.setText(f"x = {pos.x()}    y = {pos.y()}")

        self._half_seconds_left -= 1
        new_count = (self._half_seconds_left + 1) // 2
        if new_count != self._remaining:
            self._remaining = new_count
            self._countdown_lbl.setText(f"{self._remaining}")

        if self._half_seconds_left <= 0:
            self._timer.stop()
            self._capture()

    def _capture(self) -> None:
        pos = QCursor.pos()
        self.picked.emit(pos.x(), pos.y())
        self.accept()
