"""Modal countdown dialog for capturing the user's chosen window.

UX: user clicks "🔍 창 잡기" → this dialog shows "5초 안에 원하는 창을
활성화하세요…" with a live countdown → after the timer expires it
reads ``GetForegroundWindow`` and emits the resulting title.

Why countdown rather than "click on a window": tracking which window
the cursor is hovering would need a global mouse hook (`SetWindowsHookEx`)
which is way more invasive. Letting the user Alt-Tab to their target
window is just as fast and uses APIs we already have.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import win_window as ww
from .theme import C


class WindowPickerDialog(QDialog):
    picked = Signal(str, int, int, int, int)
    """``(title, x, y, w, h)`` — current window bounds, useful when the
    user wants to stamp "this exact position" into the action form."""

    def __init__(self, parent: Optional[QWidget] = None, countdown_s: int = 5) -> None:
        super().__init__(parent)
        self.setWindowTitle("창 잡기")
        self.setModal(False)
        self.setMinimumWidth(380)
        self._remaining = max(1, int(countdown_s))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(10)

        title = QLabel("🔍 창 잡기")
        title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', sans-serif;"
            f"font-size: 18px; font-weight: 600; color: {C['on-surface']};"
        )
        outer.addWidget(title)

        instructions = QLabel(
            "원하는 창을 활성화한 채로 카운트다운이 끝나길 기다려 주세요.\n"
            "Alt+Tab 으로 창을 바꾸거나, 그 창을 클릭하면 돼요."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            f"color: {C['on-surface-variant']}; font-size: 12px;"
        )
        outer.addWidget(instructions)

        self._countdown_lbl = QLabel(self._countdown_text())
        self._countdown_lbl.setAlignment(Qt.AlignCenter)
        self._countdown_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
            f"font-size: 36px; font-weight: 700;"
            f"color: {C['primary']}; padding: 12px;"
        )
        outer.addWidget(self._countdown_lbl)

        # Live preview of the foreground window — updates each tick so
        # the user can see the picker working *before* the countdown
        # ends.
        self._preview_lbl = QLabel("(활성 창 감지 중…)")
        self._preview_lbl.setWordWrap(True)
        self._preview_lbl.setStyleSheet(
            f"color: {C['on-surface']}; font-size: 12px;"
            f"background-color: {C['surface-container-low']};"
            f"border: 1px solid {C['outline-variant']};"
            f"border-radius: 6px; padding: 8px 10px;"
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
        # Stash the elapsed-since-start in half-seconds so the
        # countdown decrements once per second while the preview
        # refreshes twice per second.
        self._half_seconds_left = self._remaining * 2

    def _countdown_text(self) -> str:
        return f"{self._remaining}"

    def _tick(self) -> None:
        # Refresh preview every tick so the user sees what's about to
        # be captured.
        info = ww.get_foreground_window()
        if info is not None:
            label = info.title.strip() or "(제목 없음)"
            self._preview_lbl.setText(
                f"<b>{label}</b><br>"
                f"<span style='color: {C['on-surface-variant']};'>"
                f"위치 {info.x},{info.y} · 크기 {info.w}×{info.h}</span>"
            )
        else:
            self._preview_lbl.setText("(활성 창 감지 중…)")

        self._half_seconds_left -= 1
        # Decrement displayed counter once per second.
        new_count = (self._half_seconds_left + 1) // 2
        if new_count != self._remaining:
            self._remaining = new_count
            self._countdown_lbl.setText(self._countdown_text())

        if self._half_seconds_left <= 0:
            self._timer.stop()
            self._capture()

    def _capture(self) -> None:
        info = ww.get_foreground_window()
        if info is None:
            self._preview_lbl.setText(
                "활성 창을 잡지 못했어요. 다시 시도해 주세요."
            )
            return
        self.picked.emit(info.title, info.x, info.y, info.w, info.h)
        self.accept()
