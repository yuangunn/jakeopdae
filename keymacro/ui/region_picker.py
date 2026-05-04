"""Full-screen overlay for selecting a screen region by mouse drag.

Used both for setting a trigger's ``region`` and for capturing template
images. The widget covers the union of every connected screen so it works
in multi-monitor setups; the rectangle returned via :pyattr:`selected` is
in absolute screen coordinates.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QRubberBand, QWidget


class RegionPickerOverlay(QWidget):
    """Translucent overlay; emits :pyattr:`selected` once the user releases."""

    selected = Signal(int, int, int, int)  # x, y, w, h (absolute screen coords)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        # Cover the union of every available screen.
        union = QRect()
        for screen in QGuiApplication.screens():
            union = union.united(screen.geometry())
        self.setGeometry(union)
        self._screen_origin = union.topLeft()

        self._origin: Optional[QPoint] = None
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)

    # --- input ----------------------------------------------------------------

    def keyPressEvent(self, event):  # noqa: N802 - Qt naming
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        self._origin = event.position().toPoint()
        self._rubber.setGeometry(QRect(self._origin, QSize()))
        self._rubber.show()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._origin is None:
            return
        rect = QRect(self._origin, event.position().toPoint()).normalized()
        self._rubber.setGeometry(rect)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self._origin is None or event.button() != Qt.LeftButton:
            return
        rect = QRect(self._origin, event.position().toPoint()).normalized()
        self._rubber.hide()
        if rect.width() < 4 or rect.height() < 4:
            # Treat tiny boxes as accidental clicks and let the user redraw.
            self._origin = None
            return

        # Widget coords -> absolute screen coords.
        screen_x = self._screen_origin.x() + rect.x()
        screen_y = self._screen_origin.y() + rect.y()
        self.selected.emit(screen_x, screen_y, rect.width(), rect.height())
        self.close()

    # --- painting -------------------------------------------------------------

    def paintEvent(self, _event):  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        pen = QPen(QColor(255, 200, 50, 220))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
