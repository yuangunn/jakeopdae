"""Static preflight lint — flags problems in a Macro before run.

Pydantic catches single-field invariants at construction time (empty
selectors, bad weekdays, etc.). The preflight pass adds *cross-step*
and *disk-state* checks that can't be expressed at the field level:

    - missing template file on disk → "템플릿 없음"
    - dangling on_success_goto target → "goto 깨짐"
    - duplicate step IDs in the macro → "중복 ID"

These are the cases where a YAML can be valid in isolation but still
fail at runtime, so they're the ones the lint protects against.
"""

from __future__ import annotations

from pathlib import Path

from keymacro.core.preflight import lint_macro, issues_by_step
from keymacro.models import (
    ImageTrigger,
    KeyAction,
    Macro,
    Region,
    Step,
    TimeTrigger,
)


def _step(sid: str, **kw) -> Step:
    defaults = dict(
        id=sid, name=sid,
        trigger=TimeTrigger(delay_s=0),
        action=KeyAction(keys="enter"),
    )
    defaults.update(kw)
    return Step(**defaults)


# --- template existence ----------------------------------------------------


def test_missing_template_file_is_flagged(tmp_path: Path):
    step = _step(
        "s1",
        trigger=ImageTrigger(
            template="missing.png",
            region=Region(x=0, y=0, w=100, h=100),
        ),
    )
    issues = lint_macro(Macro(name="t", steps=[step]), tmp_path)
    assert any(i.label == "템플릿 없음" for i in issues)


def test_template_present_passes(tmp_path: Path):
    (tmp_path / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    step = _step(
        "s1",
        trigger=ImageTrigger(
            template="ok.png",
            region=Region(x=0, y=0, w=100, h=100),
        ),
    )
    issues = lint_macro(Macro(name="t", steps=[step]), tmp_path)
    assert all(i.label != "템플릿 없음" for i in issues)


def test_unsaved_macro_skips_template_check():
    """``macro_dir`` is None when the macro has never been saved.
    Skipping the disk check avoids flagging every brand-new macro.
    """
    step = _step(
        "s1",
        trigger=ImageTrigger(
            template="some.png",
            region=Region(x=0, y=0, w=100, h=100),
        ),
    )
    issues = lint_macro(Macro(name="t", steps=[step]), None)
    assert all(i.label != "템플릿 없음" for i in issues)


# --- goto routing ----------------------------------------------------------


def test_dangling_goto_flagged():
    a = _step("a", on_success_goto="ghost")
    b = _step("b")
    issues = lint_macro(Macro(name="t", steps=[a, b]), None)
    assert any(i.label == "goto 깨짐" and i.step_id == "a" for i in issues)


def test_valid_goto_passes():
    a = _step("a", on_success_goto="b")
    b = _step("b")
    issues = lint_macro(Macro(name="t", steps=[a, b]), None)
    assert all(i.label != "goto 깨짐" for i in issues)


# --- structure / IO --------------------------------------------------------


def test_clean_macro_has_no_issues(tmp_path: Path):
    a = _step("a")
    b = _step("b", on_success_goto="a")
    issues = lint_macro(Macro(name="t", steps=[a, b]), tmp_path)
    assert issues == []


def test_grouped_by_step_id():
    a = _step("a", on_success_goto="ghost")
    b = _step("b")
    grouped = issues_by_step(lint_macro(Macro(name="t", steps=[a, b]), None))
    assert "a" in grouped
    assert "b" not in grouped
    assert all(i.severity == "error" for i in grouped["a"])
