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

from ..core.preflight import StepIssue
from ..models import Step
from .empty_state import EmptyState
from .step_card import StepCard
from .theme import C


class StepListPanel(QWidget):
    add_requested = Signal()
    selected = Signal(int)
    edit_requested = Signal(int)
    """Forwarded from a card's "✏ 편집" button or double-click on the
    card body. MainWindow opens the StepEditDialog for that row."""
    delete_requested = Signal(int)
    duplicate_requested = Signal(int)
    test_requested = Signal(int)
    """Fired when the user picks "이 단계만 테스트" from a card's
    right-click menu. Forwarded to MainWindow which spawns a one-step
    ad-hoc run."""
    move_up_requested = Signal(int)
    move_down_requested = Signal(int)
    reorder_requested = Signal(int, int)
    """``(src_row, target_index)`` after a drag-drop. The host adjusts
    indices to do the correct ``pop + insert``."""
    examples_requested = Signal()
    """Fired when the empty-state's "📚 예제 살펴보기" button is clicked."""
    preview_failure_requested = Signal(int)
    """Fired when the user clicks "📷 실패 화면" on an errored card."""
    mode_toggled = Signal(str)
    """Emitted with ``"sequential"`` or ``"parallel"`` when the user
    flips the mode pill in the header."""

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

        # Mode toggle — clicking flips between sequential and
        # parallel. ``set_mode`` (called by MainWindow when a macro
        # loads) updates the visual without firing the signal.
        self._mode = "sequential"
        self._mode_btn = QPushButton("▶ 순차")
        self._mode_btn.setProperty("role", "ghost")
        self._mode_btn.setCursor(Qt.PointingHandCursor)
        self._mode_btn.setToolTip(
            "순차: 단계 1→2→3 차례로 실행\n"
            "동시: 모든 단계의 트리거를 한꺼번에 감시 → 매칭되는 게 발사",
        )
        self._mode_btn.clicked.connect(self._on_mode_clicked)
        header.addWidget(self._mode_btn)

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
            card.edit_requested.connect(self.edit_requested)
            card.delete_requested.connect(self.delete_requested)
            card.duplicate_requested.connect(self.duplicate_requested)
            card.test_requested.connect(self.test_requested)
            card.preview_failure_requested.connect(self.preview_failure_requested)
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

    def set_issues(self, issues_by_id: dict[str, list[StepIssue]]) -> None:
        """Push preflight-lint results down to every card.

        Cards keyed by their step's ``id``; cards not in the dict get
        an empty list (clears stale badges)."""
        for card in self._cards:
            card.set_issues(issues_by_id.get(card._step.id, []))

    def set_step_failure(self, row: int, *, has_capture: bool) -> None:
        """Toggle the error state + capture-preview button on a card.

        Called from MainWindow when the runner's ``failure_capture``
        signal fires (we know there's an image to show), or when a fresh
        attempt starts (we're clearing stale state)."""
        if 0 <= row < len(self._cards):
            self._cards[row].set_error(has_capture, with_capture=has_capture)

    def selected_row(self) -> int:
        return self._selected_row

    def renumber(self) -> None:
        for i, card in enumerate(self._cards):
            card.set_row(i)

    def _fire_move(self, signal) -> None:
        if self._selected_row >= 0:
            signal.emit(self._selected_row)

    # --- run mode toggle ----------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """Update the displayed mode without emitting a signal — used
        by the host when loading a macro from disk."""
        if mode not in ("sequential", "parallel"):
            mode = "sequential"
        self._mode = mode
        if mode == "parallel":
            self._mode_btn.setText("⇄ 동시")
        else:
            self._mode_btn.setText("▶ 순차")

    def _on_mode_clicked(self) -> None:
        new_mode = "parallel" if self._mode == "sequential" else "sequential"
        self.set_mode(new_mode)
        self.mode_toggled.emit(new_mode)
