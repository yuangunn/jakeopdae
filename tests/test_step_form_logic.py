"""Light tests for the few non-Qt-dependent helpers in the GUI layer.

Anything that needs a QApplication is skipped automatically when PySide6
is not available; CI without a display will still run the rest of the
suite.
"""

from __future__ import annotations

import pytest


pyside6 = pytest.importorskip("PySide6")  # noqa: F841


def test_template_capture_slug_is_filesystem_safe():
    from keymacro.ui.template_capture import _safe_slug

    assert _safe_slug("hello world") == "hello-world"
    assert _safe_slug("strange/chars*are<gone>") == "strange-chars-are-gone"
    assert _safe_slug("") == "template"
