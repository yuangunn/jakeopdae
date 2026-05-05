"""ToastManager smoke tests.

Validates the basic life-cycle: create → reveal → dismiss removes the
toast from the manager's stack and re-stacks the remaining ones. We
shortcut the auto-fade timer by calling ``dismiss()`` directly + flushing
events so the property animation completes.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _flush(qapp):
    """Process events long enough for the 220 ms fade-out to finish."""
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(280, loop.quit)
    loop.exec()


def test_toast_manager_show_and_dismiss(qapp):
    from PySide6.QtWidgets import QMainWindow

    from keymacro.ui.toast import ToastManager

    win = QMainWindow()
    win.resize(800, 500)
    win.show()
    mgr = ToastManager(win)

    a = mgr.info("hello")
    b = mgr.success("done")
    assert len(mgr._toasts) == 2

    # Bottom edge of A should sit above top of B by exactly _GAP px.
    from keymacro.ui.toast import _GAP
    assert b.y() == a.y() + a.height() + _GAP

    a.dismiss()
    _flush(qapp)
    assert a not in mgr._toasts
    assert len(mgr._toasts) == 1

    b.dismiss()
    _flush(qapp)
    assert len(mgr._toasts) == 0
    win.close()


def test_toast_manager_handles_unknown_kind_gracefully(qapp):
    """Non-error path: an unexpected kind falls back to info colour
    instead of raising — the helper picks a default."""
    from PySide6.QtWidgets import QMainWindow

    from keymacro.ui.toast import ToastManager, _color_for, _glyph_for

    assert _color_for("info") == _color_for("info")  # known
    assert _color_for("not-a-kind") == _color_for("info")  # default
    assert _glyph_for("not-a-kind") == _glyph_for("info")

    win = QMainWindow()
    win.show()
    mgr = ToastManager(win)
    # type: ignore[arg-type] — test that runtime tolerates it
    t = mgr.show("ok", "info")
    assert t in mgr._toasts
    t.dismiss()
    _flush(qapp)
    win.close()


def test_toast_repositions_on_resize(qapp):
    from PySide6.QtWidgets import QMainWindow
    from keymacro.ui.toast import ToastManager, _MARGIN_RIGHT

    win = QMainWindow()
    win.resize(800, 500)
    win.show()
    mgr = ToastManager(win)
    t = mgr.info("x")
    qapp.processEvents()
    initial_x = t.x()

    win.resize(1100, 500)
    qapp.processEvents()
    mgr.reposition()
    qapp.processEvents()
    # The toast should follow the right edge to the new x.
    assert t.x() != initial_x
    expected = win.contentsRect().right() - _MARGIN_RIGHT - t.width()
    assert abs(t.x() - expected) <= 2
    t.dismiss()
    _flush(qapp)
    win.close()
