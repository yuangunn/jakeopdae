"""Per-user macro library.

Tracks recent + pinned macro files, plus user-added folder roots whose
``*.yaml`` children should always show up in the sidebar. The schema is
intentionally tiny — paths only, plus a cached macro name for display.

Persists at ``%LOCALAPPDATA%\\keymacro\\library.json`` on Windows;
``$XDG_DATA_HOME/keymacro/library.json`` (or ``~/.local/share/...``) on
POSIX. Corrupt files are silently replaced with an empty library so a
broken cache file never blocks the GUI from opening.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


_MAX_RECENT_NON_PINNED = 12


class LibraryEntry(BaseModel):
    path: str
    name: str = ""
    pinned: bool = False
    last_opened_at: float = 0.0


class Library(BaseModel):
    entries: list[LibraryEntry] = Field(default_factory=list)
    folder_roots: list[str] = Field(default_factory=list)

    # --- lookup ---------------------------------------------------------

    @staticmethod
    def _norm(p: str | Path) -> str:
        try:
            return str(Path(p).resolve())
        except Exception:
            return str(Path(p))

    def find(self, path: str | Path) -> Optional[LibraryEntry]:
        target = self._norm(path)
        for e in self.entries:
            if self._norm(e.path) == target:
                return e
        return None

    # --- mutations ------------------------------------------------------

    def add_recent(self, path: str | Path, name: str = "") -> LibraryEntry:
        norm = self._norm(path)
        existing = self.find(norm)
        if existing is not None:
            existing.last_opened_at = time.time()
            if name:
                existing.name = name
            self._prune_recent()
            return existing

        entry = LibraryEntry(path=norm, name=name, last_opened_at=time.time())
        self.entries.append(entry)
        self._prune_recent()
        return entry

    def _prune_recent(self) -> None:
        pinned = [e for e in self.entries if e.pinned]
        not_pinned = sorted(
            [e for e in self.entries if not e.pinned],
            key=lambda e: e.last_opened_at,
            reverse=True,
        )
        self.entries = pinned + not_pinned[:_MAX_RECENT_NON_PINNED]

    def toggle_pin(self, path: str | Path) -> Optional[bool]:
        entry = self.find(path)
        if entry is None:
            return None
        entry.pinned = not entry.pinned
        return entry.pinned

    def remove(self, path: str | Path) -> bool:
        target = self._norm(path)
        before = len(self.entries)
        self.entries = [e for e in self.entries if self._norm(e.path) != target]
        return len(self.entries) != before

    def add_folder(self, folder: str | Path) -> bool:
        target = self._norm(folder)
        if target in (self._norm(f) for f in self.folder_roots):
            return False
        self.folder_roots.append(target)
        return True

    def remove_folder(self, folder: str | Path) -> bool:
        target = self._norm(folder)
        before = len(self.folder_roots)
        self.folder_roots = [
            f for f in self.folder_roots if self._norm(f) != target
        ]
        return len(self.folder_roots) != before


# ---------------------------------------------------------------------------
# Disk persistence
# ---------------------------------------------------------------------------


def library_path() -> Path:
    """Return the on-disk path of the library file for the current OS."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(
            Path.home() / ".local" / "share"
        )
    return Path(base) / "keymacro" / "library.json"


def load_library(path: Optional[Path] = None) -> Library:
    p = path or library_path()
    if not p.exists():
        return Library()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return Library.model_validate(data)
    except Exception:
        return Library()


def save_library(library: Library, path: Optional[Path] = None) -> None:
    p = path or library_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(library.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(p)
