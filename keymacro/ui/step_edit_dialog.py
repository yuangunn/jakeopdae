"""Modeless popup wrapping :class:`StepForm` for a single step.

The form panel used to live in the main window's right-hand splitter
slot, which forced the whole window to be ~1100 px wide just to keep
the form's labels and controls legible. Most macro UIs (V2.x family)
keep the main surface compact (sub-700 px) and pop a separate edit
window only when the user is actively editing a step — that's the
pattern we adopt here.

Usage:
    dlg = StepEditDialog(parent)
    dlg.load_step(step, row)        # row stashed for change-back
    dlg.show()
    dlg.step_changed.connect(...)   # form-edit notifications

The dialog is reused — opening another step calls ``load_step`` again
on the same instance rather than spawning a new window. Signals from
the inner :class:`StepForm` are re-emitted on the dialog so the host
doesn't need to reach through ``dlg.form.…``.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import Step
from .step_form import StepForm


class StepEditDialog(QDialog):
    """Hosts a :class:`StepForm` in its own window."""

    step_changed = Signal()
    pick_region_requested = Signal()
    capture_template_requested = Signal()
    pick_web_selector_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("단계 편집")
        # Modeless so the user can keep clicking around the main window
        # (e.g. picking other steps in the list) while the editor is
        # open. ``load_step`` swaps the contents in place.
        self.setModal(False)
        # Window flags: a regular dialog frame with a system close
        # button. We don't want it to be considered "tool" — the user
        # may want to maximize / move it to a second monitor.
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        # Default size: just wide enough for the widest sub-form's
        # buttons (image trigger's "화면에서 영역 그리기 + 지금 캡처"
        # row) without the dialog feeling roomy. Stays open across
        # different steps so users can resize once and forget.
        self.resize(520, 720)
        self.setMinimumSize(440, 420)

        # ``_current_row`` lets the host map form-changed signals back
        # to the right macro step without separately tracking the
        # selected row. ``-1`` means "nothing loaded yet".
        self._current_row = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self.form = StepForm()
        scroll.setWidget(self.form)
        outer.addWidget(scroll, 1)

        # Re-emit form signals — the host wired them on ``self.form``
        # before; preserve that interface so ``MainWindow`` doesn't
        # have to know whether the form lives in a splitter or here.
        self.form.step_changed.connect(self.step_changed)
        self.form.pick_region_requested.connect(self.pick_region_requested)
        self.form.capture_template_requested.connect(
            self.capture_template_requested,
        )
        self.form.pick_web_selector_requested.connect(
            self.pick_web_selector_requested,
        )

    # --- public API forwarded onto the inner form -------------------

    def load_step(self, step: Step, row: int) -> None:
        self._current_row = row
        self.form.load_step(step)
        self.setWindowTitle(
            f"단계 편집 — {step.name or step.id}"
        )

    def to_step(self) -> Step:
        return self.form.to_step()

    def current_row(self) -> int:
        """Macro-step index this dialog was opened on. ``-1`` if no
        step has been loaded yet."""
        return self._current_row

    def set_template(self, rel: str) -> None:
        self.form.set_template(rel)

    def set_region(self, x: int, y: int, w: int, h: int) -> None:
        self.form.set_region(x, y, w, h)

    def set_web_selector(self, field_key: str, selector: str) -> None:
        self.form.set_web_selector(field_key, selector)
