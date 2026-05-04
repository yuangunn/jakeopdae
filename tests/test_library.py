"""Macro library: recent + pinned + folder roots."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from keymacro.storage.library import (
    Library,
    LibraryEntry,
    load_library,
    save_library,
)


def _write_dummy(path: Path) -> Path:
    path.write_text("name: x\nsteps: []\n", encoding="utf-8")
    return path


def test_add_recent_creates_entry(tmp_path):
    p = _write_dummy(tmp_path / "foo.yaml")
    lib = Library()
    lib.add_recent(p, name="foo")
    entry = lib.find(p)
    assert entry is not None
    assert entry.name == "foo"
    assert entry.last_opened_at > 0


def test_add_recent_dedups_and_updates_timestamp(tmp_path):
    p = _write_dummy(tmp_path / "foo.yaml")
    lib = Library()
    lib.add_recent(p)
    t1 = lib.find(p).last_opened_at
    time.sleep(0.01)
    lib.add_recent(p, name="updated")
    assert len(lib.entries) == 1
    e = lib.find(p)
    assert e.last_opened_at > t1
    assert e.name == "updated"


def test_recent_pruned_at_max(tmp_path):
    lib = Library()
    for i in range(20):
        p = _write_dummy(tmp_path / f"file{i}.yaml")
        lib.add_recent(p)
    # 12 max non-pinned, 0 pinned -> at most 12 entries
    assert len(lib.entries) <= 12


def test_pinned_kept_beyond_recent_cap(tmp_path):
    lib = Library()
    star = _write_dummy(tmp_path / "star.yaml")
    lib.add_recent(star)
    assert lib.toggle_pin(star) is True
    for i in range(20):
        p = _write_dummy(tmp_path / f"file{i}.yaml")
        lib.add_recent(p)
    e = lib.find(star)
    assert e is not None and e.pinned is True


def test_toggle_pin_returns_new_state(tmp_path):
    p = _write_dummy(tmp_path / "foo.yaml")
    lib = Library()
    lib.add_recent(p)
    assert lib.toggle_pin(p) is True
    assert lib.toggle_pin(p) is False


def test_toggle_pin_returns_none_for_unknown(tmp_path):
    lib = Library()
    assert lib.toggle_pin(tmp_path / "absent.yaml") is None


def test_remove_purges_entry(tmp_path):
    p = _write_dummy(tmp_path / "foo.yaml")
    lib = Library()
    lib.add_recent(p)
    assert lib.remove(p) is True
    assert lib.find(p) is None
    assert lib.remove(p) is False


def test_add_folder_dedups(tmp_path):
    lib = Library()
    assert lib.add_folder(tmp_path) is True
    assert lib.add_folder(tmp_path) is False
    assert len(lib.folder_roots) == 1


def test_round_trip_via_disk(tmp_path):
    p = _write_dummy(tmp_path / "foo.yaml")
    lib = Library()
    lib.add_recent(p, name="Foo")
    lib.toggle_pin(p)
    lib.add_folder(tmp_path)

    library_file = tmp_path / "library.json"
    save_library(lib, library_file)
    loaded = load_library(library_file)

    e = loaded.find(p)
    assert e is not None and e.pinned and e.name == "Foo"
    assert any(Path(f).resolve() == tmp_path.resolve() for f in loaded.folder_roots)


def test_load_missing_returns_empty(tmp_path):
    lib = load_library(tmp_path / "absent.json")
    assert lib.entries == []
    assert lib.folder_roots == []


def test_load_corrupt_returns_empty(tmp_path):
    p = tmp_path / "corrupt.json"
    p.write_text("not valid json", encoding="utf-8")
    lib = load_library(p)
    assert lib.entries == []


def test_save_is_atomic(tmp_path):
    """A successful save replaces the target via a single rename."""
    lib = Library()
    lib.add_recent(_write_dummy(tmp_path / "foo.yaml"))
    out = tmp_path / "library.json"
    save_library(lib, out)
    assert out.exists()
    assert not (tmp_path / "library.json.tmp").exists()
