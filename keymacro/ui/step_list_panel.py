"""Compact vertical scrolling list of StepCard widgets."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import Step
from .empty_state import EmptyState
from .step_card import StepCard
from .theme import C


class StepListPanel(QWidget):
    add_requested = Signal()
    selected = Signal(int)
    delete_requested = Signal(int)
    duplicate_requested = Signal(int)
    move_up_requested = Signal(int)
    move_down_requested = Signal(int)
    reorder_requested = Signal(int, int)
    """``(src_row, target_index)`` after a drag-drop. The host adjusts
    indices to do the correct ``pop + insert``."""
    examples_requested = Signal()
    """Fired when the empty-state's "📚 예제 살펴보기" button is clicked."""

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header row: "단계" + count + add button
        header = QHBoxLayout()
        header.setContentsMargins(14, 10, 14, 6)
        header.setSpacing(8)
        title = QLabel("단계")
        title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', 'Pretendard Variable', sans-serif;"
            f"font-size: 14px; font-weight: 600; color: {C['on-surface']};"
        )
        header.addWidget(title)

        self._count_lbl = QLabel("0개")
        self._count_lbl.setStyleSheet(
            f"color: {C['on-surface-variant']};"
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
            f"font-size: 10px;"
        )
        header.addWidget(self._count_lbl)
        header.addStretch()

        # Reorder buttons inline with header
        self._up_btn = QPushButton("▲")
        self._up_btn.setProperty("role", "icon-mini")
        self._up_btn.setToolTip("선택한 단계를 위로")
        self._up_btn.clicked.connect(lambda: self._fire_move(self.move_up_requested))
        self._down_btn = QPushButton("▼")
        self._down_btn.setProperty("role", "icon-mini")
        self._down_btn.setToolTip("선택한 단계를 아래로")
        self._down_btn.clicked.connect(lambda: self._fire_move(self.move_down_requested))
        header.addWidget(self._up_btn)
        header.addWidget(self._down_btn)

        self._add_btn = QPushButton("＋  단계 추가")
        self._add_btn.setProperty("role", "primary")
        self._add_btn.clicked.connect(self.add_requested)
        header.addWidget(self._add_btn)
        outer.addLayout(header)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(14, 4, 14, 14)
        self._inner_layout.setSpacing(8)
        self._inner_layout.addStretch()
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

        self._empty: Optional[EmptyState] = None
        self._cards: list[StepCard] = []
        self._selected_row = -1

    # --- public API -----------------------------------------------------

    def set_steps(
        self,
        steps: list[Step],
        select_index: int = 0,
        *,
        show_examples_button: bool = False,
    ) -> None:
        for card in self._cards:
            self._inner_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        if self._empty is not None:
            self._inner_layout.removeWidget(self._empty)
            self._empty.deleteLater()
            self._empty = None

        self._count_lbl.setText(f"{len(steps)}개")

        if not steps:
            self._empty = EmptyState(show_examples_button=show_examples_button)
            self._empty.add_requested.connect(self.add_requested)
            self._empty.examples_requested.connect(self.examples_requested)
            self._inner_layout.insertWidget(0, self._empty)
            self._selected_row = -1
            return

        for i, step in enumerate(steps):
            card = StepCard(step, i)
            card.selected.connect(self.selected)
            card.delete_requested.connect(self.delete_requested)
            card.duplicate_requested.connect(self.duplicate_requested)
            card.reorder_requested.connect(self.reorder_requested)
            self._cards.append(card)
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, card)

        idx = max(0, min(select_index, len(steps) - 1))
        self.set_selected(idx)

    def update_step(self, row: int, step: Step) -> None:
        if 0 <= row < len(self._cards):
            self._cards[row].update_step(step)

    def set_selected(self, row: int) -> None:
        self._selected_row = row
        for i, card in enumerate(self._cards):
            card.set_active(i == row)

    def set_step_state(self, row: int, *, active: bool = False, error: bool = False) -> None:
        if 0 <= row < len(self._cards):
            if error:
                self._cards[row].set_error(True)
            else:
                self._cards[row].set_active(active)

    def selected_row(self) -> int:
        return self._selected_row

    def renumber(self) -> None:
        for i, card in enumerate(self._cards):
            card.set_row(i)

    def _fire_move(self, signal) -> None:
        if self._selected_row >= 0:
            signal.emit(self._selected_row)
