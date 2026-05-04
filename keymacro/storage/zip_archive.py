"""Macro archive (zip) import / export.

A macro archive bundles the YAML file together with every template image
it references, so a macro can be sent / shared as a single ``.kma`` file
(``.kma`` is just a zip with a fixed layout).

Layout inside the archive::

    <name>.yaml
    templates/<...>          # mirrors the macro_dir layout

The importer rewrites template paths in the YAML to be relative to the
extracted directory (they already are, by convention; we just verify).
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Iterable

from ..models.macro import Macro
from ..models.trigger import ImageTrigger
from .yaml_repo import load_macro, save_macro


def _collect_template_paths(macro: Macro) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for step in macro.steps:
        if isinstance(step.trigger, ImageTrigger):
            t = step.trigger.template
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def export_macro(
    macro: Macro,
    macro_dir: str | Path,
    archive_path: str | Path,
    *,
    yaml_name: str = "macro.yaml",
) -> Path:
    """Write a self-contained ``.kma`` archive.

    ``macro_dir`` is where the macro's templates currently live; relative
    paths inside the macro are resolved against it.
    """
    macro_dir = Path(macro_dir)
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. The macro YAML itself.
        zf.writestr(
            yaml_name,
            _yaml_bytes_for_macro(macro),
        )
        # 2. Every template the macro references, preserving its relative path.
        for rel in _collect_template_paths(macro):
            src = (macro_dir / rel).resolve()
            if not src.exists():
                raise FileNotFoundError(f"template missing: {src}")
            zf.write(src, arcname=rel)
    return archive_path


def import_macro(archive_path: str | Path, dest_dir: str | Path) -> tuple[Macro, Path]:
    """Extract an archive into ``dest_dir`` and load the macro it contains.

    Returns ``(macro, yaml_path)``. The yaml path is anchored under
    ``dest_dir`` so the runner resolves templates correctly.
    """
    archive_path = Path(archive_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zf:
        # Reject any path traversal attempts before extracting.
        for info in zf.infolist():
            target = (dest_dir / info.filename).resolve()
            if not str(target).startswith(str(dest_dir.resolve())):
                raise ValueError(f"unsafe path in archive: {info.filename}")
        zf.extractall(dest_dir)
        # Find a yaml at the archive root.
        yamls = [n for n in zf.namelist() if n.endswith(".yaml") and "/" not in n]
        if not yamls:
            raise ValueError("archive contains no top-level macro YAML")
        yaml_name = yamls[0]

    yaml_path = dest_dir / yaml_name
    macro = load_macro(yaml_path)
    return macro, yaml_path


def _yaml_bytes_for_macro(macro: Macro) -> bytes:
    """Serialize a macro to YAML bytes by going through the disk path; this
    keeps a single source of truth for the on-disk format."""
    import io
    import yaml

    data = macro.model_dump(mode="json", exclude_defaults=False)
    buf = io.StringIO()
    yaml.safe_dump(data, buf, sort_keys=False, allow_unicode=True)
    return buf.getvalue().encode("utf-8")


# Re-export for the storage package facade.
__all__ = ["export_macro", "import_macro"]
