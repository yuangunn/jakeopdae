"""Full-screen overlay for picking a single click point.

Same pattern as :class:`RegionPickerOverlay` but emits a single
``(x, y)`` instead of a rectangle. Used by the click action's "현재
마우스 위치 잡기" button — replaced the original 5-second countdown
with this direct point-and-click flow because the countdown felt
arbitrary and the user couldn't tell it was working.

Multi-monitor: the overlay spans the union of every connected
screen, so the user can click anywhere on any monitor and the
emitted coordinates are absolute virtual-desktop coords (matching
what ``ClickAction`` expects).

Cancel: Esc closes without emitting; right-click also cancels (often
a more natural reflex than fishing for the Esc key).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ClickPickerOverlay(QWidget):
    """Translucent fullscreen overlay; emits ``picked(x, y)`` on
    left-click, ``cancelled`` on Esc / right-click."""

    picked = Signal(int, int)  # absolute desktop coords
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

        union = QRect()
        for screen in QGuiApplication.screens():
            union = union.united(screen.geometry())
        self.setGeometry(union)
        self._screen_origin = union.topLeft()

        # Track the cursor for the live preview (e.g. "x=1024, y=512")
        # rendered next to the crosshair.
        self._cursor_pos = QCursor.pos()
        # Fall back to the centre of the union so the preview still
        # shows something even before the first mouseMoveEvent.

    # --- input ----------------------------------------------------------------

    def keyPressEvent(self, event):  # noqa: N802 — Qt override
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 — Qt override
        if event.button() == Qt.RightButton:
            self.cancelled.emit()
            self.close()
            return
        if event.button() != Qt.LeftButton:
            return
        # Local widget point + screen origin → absolute desktop coord.
        local = event.position().toPoint()
        screen_x = self._screen_origin.x() + local.x()
        screen_y = self._screen_origin.y() + local.y()
        self.picked.emit(screen_x, screen_y)
        self.close()

    def mouseMoveEvent(self, event):  # noqa: N802 — Qt override
        # Refresh the live preview chip near the cursor.
        local = event.position().toPoint()
        self._cursor_pos = QPoint(
            self._screen_origin.x() + local.x(),
            self._screen_origin.y() + local.y(),
        )
        self.update()

    # --- painting -------------------------------------------------------------

    def paintEvent(self, _event):  # noqa: N802 — Qt override
        painter = QPainter(self)
        # Dim the desktop a touch so the user knows the overlay is up.
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        # Faint dashed border around the whole overlay so multi-monitor
        # users see how far the picker reaches.
        pen = QPen(QColor(255, 200, 50, 180))
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

        # Cursor crosshair + coordinate chip.
        local = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(local):
            return
        # Crosshair lines.
        cross = QPen(QColor(255, 255, 255, 180))
        cross.setWidth(1)
        cross.setStyle(Qt.DashLine)
        painter.setPen(cross)
        painter.drawLine(0, local.y(), self.width(), local.y())
        painter.drawLine(local.x(), 0, local.x(), self.height())

        # Coordinate chip — solid pill near the cursor.
        chip_w, chip_h = 130, 28
        chip_x = local.x() + 16
        chip_y = local.y() + 16
        if chip_x + chip_w > self.width():
            chip_x = local.x() - chip_w - 16
        if chip_y + chip_h > self.height():
            chip_y = local.y() - chip_h - 16
        chip = QRect(chip_x, chip_y, chip_w, chip_h)
        painter.fillRect(chip, QColor(19, 17, 14, 230))
        chip_border = QPen(QColor(232, 178, 106, 220))  # brass
        chip_border.setWidth(1)
        painter.setPen(chip_border)
        painter.drawRect(chip)
        painter.setPen(QColor(242, 235, 218))
        font = QFont("JetBrains Mono")
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(
            chip,
            Qt.AlignCenter,
            f"x={self._cursor_pos.x()}  y={self._cursor_pos.y()}",
        )
