"""Sticky bottom transport bar (compact: 64px tall, 40px buttons).

The match gauge is tinted with the active step's trigger colour while
running, so the user can tell at a glance what kind of trigger is
currently being polled (cobalt = image, sage = time, rose = pixel).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import C, STRIPE


class _MatchGauge(QWidget):
    """Horizontal track + animated fill; tint follows the active trigger."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(4)
        self._track = QFrame(self)
        self._fill = QFrame(self._track)
        self._track.setStyleSheet(
            f"background-color: {C['surface-container-highest']};"
            f"border-radius: 2px;"
        )
        self._fill_color = C["primary"]
        self._apply_fill_color()
        self._value = 0.0
        self._update_geometry()

    def _apply_fill_color(self) -> None:
        self._fill.setStyleSheet(
            f"background-color: {self._fill_color};"
            f"border-radius: 2px;"
        )

    def resizeEvent(self, e):  # noqa: N802
        self._update_geometry()
        super().resizeEvent(e)

    def set_value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, float(v)))
        self._update_geometry()

    def set_kind(self, kind: str | None) -> None:
        self._fill_color = STRIPE.get(kind or "", C["primary"])
        self._apply_fill_color()

    def _update_geometry(self) -> None:
        w = self.width()
        self._track.setGeometry(0, 0, w, 4)
        self._fill.setGeometry(0, 0, int(w * self._value), 4)


class TransportBar(QFrame):
    start_requested = Signal()
    stop_requested = Signal()
    pause_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("role", "transport-bar")
        self.setMinimumHeight(64)
        self.setMaximumHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._step_kind_lookup: dict[str, str] = {}
        self._build_ui()
        self.set_running(False)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Hotkey labels visible on the buttons themselves so the user
        # doesn't have to memorize them — the F-row is the same as
        # ``HotkeyManager`` registers (F9/F10/F11). Tooltips repeat
        # the binding for users who hover before clicking.
        self._play_btn = QPushButton("▶  시작 (F9)")
        self._play_btn.setProperty("role", "transport-play")
        self._play_btn.setCursor(Qt.PointingHandCursor)
        self._play_btn.setToolTip("매크로 시작 (F9)")
        self._play_btn.clicked.connect(self.start_requested)
        layout.addWidget(self._play_btn)

        self._pause_btn = QPushButton("⏸  일시정지 (F11)")
        self._pause_btn.setProperty("role", "transport-ghost")
        self._pause_btn.setCursor(Qt.PointingHandCursor)
        self._pause_btn.setToolTip("일시정지 / 재개 (F11)")
        self._pause_btn.clicked.connect(self.pause_requested)
        layout.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("■  정지 (F10)")
        self._stop_btn.setProperty("role", "transport-ghost")
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setToolTip("매크로 정지 (F10)")
        self._stop_btn.clicked.connect(self.stop_requested)
        layout.addWidget(self._stop_btn)

        layout.addSpacing(12)

        right = QVBoxLayout()
        right.setSpacing(4)
        self._status_lbl = QLabel("대기 중")
        self._status_lbl.setStyleSheet(
            f"color: {C['on-surface-variant']};"
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
            f"font-size: 11px;"
        )
        right.addWidget(self._status_lbl)

        self._gauge = _MatchGauge()
        right.addWidget(self._gauge)

        layout.addLayout(right, 1)

    # --- public API -----------------------------------------------------

    def set_step_kind_lookup(self, lookup: dict[str, str]) -> None:
        """Tell the bar what kind each step is so the gauge can colour itself."""
        self._step_kind_lookup = dict(lookup)

    def set_running(self, running: bool) -> None:
        self._play_btn.setEnabled(not running)
        self._pause_btn.setEnabled(running)
        self._stop_btn.setEnabled(running)
        if not running:
            self._status_lbl.setText("대기 중")
            self._gauge.set_value(0.0)
            self._gauge.set_kind(None)

    def set_status(self, text: str) -> None:
        self._status_lbl.setText(text)

    def set_match(self, step_id: str, score: float, found: bool) -> None:
        self._gauge.set_value(score)
        self._gauge.set_kind(self._step_kind_lookup.get(step_id))
        marker = "OK" if found else "··"
        self._status_lbl.setText(
            f"[{marker}] {step_id} · 신뢰도 {score:.3f}"
        )
