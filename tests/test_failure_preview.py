"""FailurePreviewDialog smoke tests.

Verifies the ndarray → QPixmap conversion path handles the three image
shapes the runner can produce: BGR (image trigger crop), grayscale
(rare), and the 1×1 placeholder (web triggers without a page).
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_bgr_image_renders(qapp):
    from keymacro.ui.failure_preview import _ndarray_to_qpixmap

    img = np.zeros((40, 60, 3), dtype=np.uint8)
    img[:, :, 0] = 200  # Blue channel — runner output is BGR
    pix = _ndarray_to_qpixmap(img)
    assert pix is not None
    assert not pix.isNull()
    assert pix.width() == 60 and pix.height() == 40


def test_placeholder_one_by_one_returns_none(qapp):
    """Runner emits this 1×1 sentinel for triggers that can't capture
    (e.g. web URL trigger when the page isn't initialised yet). The
    dialog must NOT try to render it as a real pixmap — falls back to
    the explanatory text label."""
    from keymacro.ui.failure_preview import _ndarray_to_qpixmap

    placeholder = np.zeros((1, 1, 3), dtype=np.uint8)
    assert _ndarray_to_qpixmap(placeholder) is None


def test_grayscale_renders(qapp):
    from keymacro.ui.failure_preview import _ndarray_to_qpixmap

    gray = np.zeros((20, 30), dtype=np.uint8)
    pix = _ndarray_to_qpixmap(gray)
    assert pix is not None
    assert pix.width() == 30 and pix.height() == 20


def test_dialog_with_real_image_shows_pixmap(qapp):
    from keymacro.ui.failure_preview import FailurePreviewDialog

    img = np.zeros((50, 80, 3), dtype=np.uint8)
    dlg = FailurePreviewDialog("step1", img, message="trigger timed out")
    assert dlg._image_label.pixmap() is not None
    assert not dlg._image_label.pixmap().isNull()
    dlg.close()


def test_dialog_with_placeholder_shows_explanation_text(qapp):
    """When there's no real image we want the user to see *why* there
    isn't one, not a blank rectangle."""
    from keymacro.ui.failure_preview import FailurePreviewDialog

    placeholder = np.zeros((1, 1, 3), dtype=np.uint8)
    dlg = FailurePreviewDialog("step2", placeholder)
    # No pixmap, but text fallback is set.
    assert dlg._image_label.pixmap() is None or dlg._image_label.pixmap().isNull()
    assert "캡처" in dlg._image_label.text()
    dlg.close()
