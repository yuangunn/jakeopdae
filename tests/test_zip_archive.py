"""Macro archive (.kma) round-trip."""

from __future__ import annotations

import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from keymacro.models import (
    ClickAction,
    ImageTrigger,
    Macro,
    Region,
    Step,
    TimeTrigger,
    WaitAction,
)
from keymacro.storage.zip_archive import export_macro, import_macro


def _make_macro_with_template(macro_dir: Path) -> Macro:
    tpl = (macro_dir / "templates")
    tpl.mkdir(parents=True, exist_ok=True)
    img = np.full((10, 10, 3), 128, dtype=np.uint8)
    cv2.imwrite(str(tpl / "icon.png"), img)
    return Macro(
        name="round-trip",
        steps=[
            Step(
                id="s1", name="image",
                trigger=ImageTrigger(
                    template="templates/icon.png",
                    region=Region(x=0, y=0, w=100, h=100),
                ),
                action=ClickAction(x=10, y=10),
            ),
            Step(
                id="s2", name="time",
                trigger=TimeTrigger(delay_s=0.0),
                action=WaitAction(duration_s=0.0),
            ),
        ],
    )


def test_round_trip_via_archive(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    macro = _make_macro_with_template(src)

    archive = tmp_path / "out.kma"
    export_macro(macro, src, archive)
    assert archive.exists()

    dest = tmp_path / "dest"
    loaded, yaml_path = import_macro(archive, dest)
    assert loaded == macro
    assert (dest / "templates" / "icon.png").exists()
    assert yaml_path.parent == dest


def test_export_fails_when_template_missing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    macro = Macro(
        name="x",
        steps=[
            Step(
                id="s1", name="x",
                trigger=ImageTrigger(
                    template="templates/missing.png",
                    region=Region(x=0, y=0, w=10, h=10),
                ),
                action=ClickAction(x=0, y=0),
            )
        ],
    )
    with pytest.raises(FileNotFoundError):
        export_macro(macro, src, tmp_path / "x.kma")


def test_import_rejects_path_traversal(tmp_path):
    bad = tmp_path / "evil.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../escape.txt", "no")
    with pytest.raises(ValueError):
        import_macro(bad, tmp_path / "extract")


def test_import_requires_top_level_yaml(tmp_path):
    bad = tmp_path / "no-yaml.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("only-this-file.txt", "hi")
    with pytest.raises(ValueError):
        import_macro(bad, tmp_path / "extract")
