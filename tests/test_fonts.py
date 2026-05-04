"""Bundled font registration smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_bundled_font_files_ship_with_package():
    """The 4 NotoSansKR weights must exist as package data so installs
    pick them up via the ``[tool.setuptools.package-data]`` glob."""
    pyside6 = pytest.importorskip("PySide6")  # noqa: F841
    from keymacro.ui.fonts import font_paths

    paths = list(font_paths())
    assert len(paths) == 4, "expected exactly 4 NotoSansKR weights bundled"
    for p in paths:
        assert isinstance(p, Path)
        assert p.exists(), f"missing bundled font: {p}"
        assert p.stat().st_size > 100_000, f"truncated font file: {p}"
        assert p.name.startswith("NotoSansKR-")
        assert p.name.endswith(".ttf")


def test_load_bundled_fonts_registers_family():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from keymacro.ui.fonts import load_bundled_fonts

    families = load_bundled_fonts()
    # We expect at least one family (Noto Sans KR or its variants)
    assert any("Noto" in f for f in families), (
        f"expected 'Noto Sans KR' family registered, got: {families}"
    )
