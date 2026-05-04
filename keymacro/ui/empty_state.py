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
    examples_requested = Signal()

    def __init__(self, *, show_examples_button: bool = False) -> None:
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

        if show_examples_button:
            body_text = (
                "위의 [＋ 단계 추가]로 직접 만들거나\n"
                "[📚 예제 살펴보기]에서 미리 만들어둔 매크로를 참고해 보세요."
            )
        else:
            body_text = "위의 [＋ 단계 추가] 버튼을 눌러\n첫 단계를 만들어 보세요."
        body = QLabel(body_text)
        body.setAlignment(Qt.AlignCenter)
        body.setStyleSheet(
            f"color: {C['on-surface-variant']}; font-size: 12px; line-height: 1.5;"
        )
        layout.addWidget(body)
        layout.addSpacing(14)

        # Action row — primary "+ 단계 추가" plus optional "예제 살펴보기".
        wrap = QFrame()
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.addStretch()

        if show_examples_button:
            ex_btn = QPushButton("📚  예제 살펴보기")
            ex_btn.setProperty("role", "ghost")
            ex_btn.setCursor(Qt.PointingHandCursor)
            ex_btn.clicked.connect(self.examples_requested)
            h.addWidget(ex_btn)

        btn = QPushButton("＋  단계 추가")
        btn.setProperty("role", "primary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.add_requested)
        h.addWidget(btn)
        h.addStretch()
        layout.addWidget(wrap)
        layout.addSpacing(16)

        rule_bot = QFrame()
        rule_bot.setProperty("role", "empty-rule")
        rule_bot.setFixedHeight(1)
        layout.addWidget(rule_bot)
        layout.addStretch()
