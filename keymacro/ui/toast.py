"""Top-right floating toast notifications.

Replaces transient ``statusBar().showMessage`` and one-line
``QMessageBox.information`` calls with non-modal cards that fade in,
sit for a few seconds, and slide away.

Why a custom widget instead of Qt's tray balloon:
    - Tray balloons are OS-skinned and look out of place against the
      dark brass theme.
    - We want stack semantics: multiple toasts visible at once, newest
      on top, click to dismiss individually.
    - Click-through must reach the underlying form. ``QFrame`` parented
      to MainWindow with mouse events handled per-widget covers this.

Anchoring strategy:
    Toasts are children of ``MainWindow`` (NOT a top-level window) so
    they stick to the window when it moves and clip naturally to the
    chrome. ``ToastManager.reposition`` is wired to ``resizeEvent`` and
    runs on every show/hide.
"""

from __future__ import annotations

from typing import Final, Literal

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

ToastKind = Literal["info", "success", "warning", "error"]


# Anchored offsets from the right + top of the parent's contents area.
_MARGIN_RIGHT: Final[int] = 16
_MARGIN_TOP: Final[int] = 14
_GAP: Final[int] = 8
_TOAST_WIDTH: Final[int] = 320
_DEFAULT_DURATION_MS: Final[int] = 3000


class Toast(QWidget):
    """A single notification card. Self-destructs after ``duration_ms``."""

    def __init__(
        self,
        parent: QWidget,
        message: str,
        kind: ToastKind = "info",
        duration_ms: int = _DEFAULT_DURATION_MS,
    ) -> None:
        # Parent is the MainWindow so the toast clips to chrome and follows
        # window moves automatically. We do NOT make this a top-level window.
        super().__init__(parent)
        self.setObjectName("toast")
        self.setProperty("role", "toast")
        self.setProperty("kind", kind)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        # Don't steal focus when the toast pops in.
        self.setFocusPolicy(Qt.NoFocus)
        self._kind = kind
        self._duration_ms = max(800, int(duration_ms))

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 10, 8, 10)
        outer.setSpacing(10)

        icon = QLabel(_glyph_for(kind))
        icon.setObjectName("toastIcon")
        icon.setProperty("kind", kind)
        icon.setFixedWidth(20)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {_color_for(kind)};"
        )
        outer.addWidget(icon, 0, Qt.AlignTop)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setObjectName("toastBody")
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        body.setStyleSheet(
            "font-family: 'Noto Sans KR', 'Pretendard Variable', sans-serif;"
            "font-size: 12px; color: #F2EBDA;"
        )
        outer.addWidget(body, 1)

        close = QPushButton("×")
        close.setObjectName("toastClose")
        close.setProperty("role", "icon-mini")
        close.setFixedSize(18, 18)
        close.setCursor(QCursor(Qt.PointingHandCursor))
        close.setToolTip("닫기")
        close.clicked.connect(self.dismiss)
        outer.addWidget(close, 0, Qt.AlignTop)

        self.setFixedWidth(_TOAST_WIDTH)
        self.adjustSize()

        # Opacity effect drives the fade-in / fade-out animations. We hold
        # references on self so Python doesn't garbage-collect them mid-anim.
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._fade_in = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade_in.setDuration(180)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

        self._fade_out = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade_out.setDuration(220)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out.finished.connect(self._finalize)

        # Auto-dismiss timer — single shot, stopped if the user clicks ×.
        self._auto = QTimer(self)
        self._auto.setSingleShot(True)
        self._auto.timeout.connect(self.dismiss)
        self._auto.setInterval(self._duration_ms)

        self._dismissing = False

    # --- public API -----------------------------------------------------

    def reveal(self) -> None:
        self.show()
        self.raise_()
        self._fade_in.start()
        self._auto.start()

    def dismiss(self) -> None:
        if self._dismissing:
            return
        self._dismissing = True
        self._auto.stop()
        self._fade_out.start()

    def mousePressEvent(self, event):  # noqa: N802 — Qt override
        # Click anywhere on the body dismisses too.
        self.dismiss()
        super().mousePressEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        return QSize(_TOAST_WIDTH, super().sizeHint().height())

    # --- internals ------------------------------------------------------

    def _finalize(self) -> None:
        # Notify manager so it can drop the reference + re-stack remaining
        # toasts. The manager is the parent's child filter — we walk up
        # via property to find it.
        mgr = self.parent().property("_toast_manager") if self.parent() else None
        if isinstance(mgr, ToastManager):
            mgr._on_toast_finished(self)
        else:
            self.deleteLater()


class ToastManager(QObject):
    """Stacks active toasts in the top-right corner of ``host``.

    The host is responsible for calling :py:meth:`reposition` from its
    own ``resizeEvent`` so toasts track window resize.
    """

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self._host = host
        self._toasts: list[Toast] = []
        # Stash a reference on the host for Toast._finalize to find us.
        host.setProperty("_toast_manager", self)

    # --- public API -----------------------------------------------------

    def show(
        self,
        message: str,
        kind: ToastKind = "info",
        duration_ms: int = _DEFAULT_DURATION_MS,
    ) -> Toast:
        toast = Toast(self._host, message, kind, duration_ms)
        self._toasts.append(toast)
        self.reposition()
        toast.reveal()
        return toast

    def info(self, message: str, *, duration_ms: int = _DEFAULT_DURATION_MS) -> Toast:
        return self.show(message, "info", duration_ms)

    def success(
        self, message: str, *, duration_ms: int = _DEFAULT_DURATION_MS,
    ) -> Toast:
        return self.show(message, "success", duration_ms)

    def warning(
        self, message: str, *, duration_ms: int = 4500,
    ) -> Toast:
        return self.show(message, "warning", duration_ms)

    def error(
        self, message: str, *, duration_ms: int = 5000,
    ) -> Toast:
        return self.show(message, "error", duration_ms)

    def reposition(self) -> None:
        """Re-stack visible toasts under the top-right corner."""
        host_rect: QRect = self._host.contentsRect()
        x_right = host_rect.right() - _MARGIN_RIGHT
        y = host_rect.top() + _MARGIN_TOP
        for t in self._toasts:
            t.adjustSize()
            t.move(x_right - t.width(), y)
            y += t.height() + _GAP

    # --- internals ------------------------------------------------------

    def _on_toast_finished(self, toast: Toast) -> None:
        try:
            self._toasts.remove(toast)
        except ValueError:
            pass
        toast.deleteLater()
        self.reposition()


# ---------------------------------------------------------------------------
# Helpers — colour / glyph mapping. Pulled inline rather than imported from
# theme.py because the toast keeps its own palette decisions; QSS handles
# the rest of the chrome.
# ---------------------------------------------------------------------------

_KIND_COLOURS: dict[str, str] = {
    "info": "#5BA8E5",      # secondary (sky)
    "success": "#86B889",   # tertiary (sage)
    "warning": "#E8B26A",   # primary (brass)
    "error": "#D9847C",     # quaternary (rose)
}

_KIND_GLYPHS: dict[str, str] = {
    "info": "ⓘ",
    "success": "✓",
    "warning": "!",
    "error": "✕",
}


def _color_for(kind: str) -> str:
    return _KIND_COLOURS.get(kind, _KIND_COLOURS["info"])


def _glyph_for(kind: str) -> str:
    return _KIND_GLYPHS.get(kind, _KIND_GLYPHS["info"])
