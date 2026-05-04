"""System tray integration.

Displayed alongside the main window so the user can keep keymacro running
in the background. The icon's context menu mirrors the run panel's
buttons (start / stop / show window / quit).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon(QObject):
    start_requested = Signal()
    stop_requested = Signal()
    show_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(self._make_icon(), parent)
        self._tray.setToolTip("keymacro")

        menu = QMenu()
        a_show = QAction("Show window", menu)
        a_start = QAction("Start", menu)
        a_stop = QAction("Stop", menu)
        a_quit = QAction("Quit", menu)
        menu.addAction(a_show)
        menu.addSeparator()
        menu.addAction(a_start)
        menu.addAction(a_stop)
        menu.addSeparator()
        menu.addAction(a_quit)
        self._tray.setContextMenu(menu)

        a_show.triggered.connect(self.show_requested)
        a_start.triggered.connect(self.start_requested)
        a_stop.triggered.connect(self.stop_requested)
        a_quit.triggered.connect(self.quit_requested)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def notify(self, title: str, msg: str) -> None:
        if self._tray.isVisible():
            self._tray.showMessage(title, msg, QSystemTrayIcon.Information, 4000)

    @staticmethod
    def _make_icon() -> QIcon:
        # Tiny built-in icon so we don't ship a binary asset.
        pix = QPixmap(32, 32)
        pix.fill()
        return QIcon(pix)
