"""Load and save :class:`Macro` instances to YAML files.

YAML was chosen over JSON for two reasons: macros are commonly hand-edited,
and YAML's support for comments + cleaner multi-line strings makes diffs
easier to review.

Template image paths inside an :class:`ImageTrigger` are stored *relative*
to the YAML file's directory; resolution happens at runtime in
:class:`~keymacro.core.runner.Runner`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..models.macro import Macro


def load_macro(path: str | Path) -> Macro:
    """Read a YAML file and validate it as a :class:`Macro`."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)
    if data is None:
        raise ValueError(f"macro file is empty: {p}")
    return Macro.model_validate(data)


def save_macro(macro: Macro, path: str | Path) -> None:
    """Serialize a :class:`Macro` to YAML, atomically.

    Writing through a sibling ``.tmp`` file and renaming on success matches
    the pattern used by the KTX project's ``state.py`` and means a crash
    mid-write cannot leave a partially-written macro on disk.
    """
    p = Path(path)
    data = macro.model_dump(mode="json", exclude_defaults=False)

    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    tmp.replace(p)
