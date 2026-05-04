"""Compact empty-state widget for an empty step list."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import C


class EmptyState(QWidget):
    add_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 36, 20, 36)
        layout.setSpacing(0)
        layout.addStretch()

        rule_top = QFrame()
        rule_top.setProperty("role", "empty-rule")
        rule_top.setFixedHeight(1)
        layout.addWidget(rule_top)
        layout.addSpacing(16)

        title = QLabel("아직 단계가 없습니다")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', 'Pretendard Variable', sans-serif;"
            f"font-size: 16px; font-weight: 600;"
            f"color: {C['on-surface']}; letter-spacing: -0.2px;"
        )
        layout.addWidget(title)
        layout.addSpacing(6)

        body = QLabel("위의 [＋ 단계 추가] 버튼을 눌러\n첫 단계를 만들어 보세요.")
        body.setAlignment(Qt.AlignCenter)
        body.setStyleSheet(
            f"color: {C['on-surface-variant']}; font-size: 12px; line-height: 1.5;"
        )
        layout.addWidget(body)
        layout.addSpacing(14)

        btn = QPushButton("＋  단계 추가")
        btn.setProperty("role", "primary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.add_requested)
        wrap = QFrame()
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.addStretch()
        h.addWidget(btn)
        h.addStretch()
        layout.addWidget(wrap)
        layout.addSpacing(16)

        rule_bot = QFrame()
        rule_bot.setProperty("role", "empty-rule")
        rule_bot.setFixedHeight(1)
        layout.addWidget(rule_bot)
        layout.addStretch()
