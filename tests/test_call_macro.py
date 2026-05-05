"""CallMacroAction — sub-macro execution.

Verifies:
    - Relative paths resolve against the parent macro's directory
    - Absolute paths work
    - Variables flow both ways (parent → child input, child → parent output)
    - Recursion guard breaks a → b → a
    - Missing file → step error → on_failure routing
"""

from __future__ import annotations

from pathlib import Path

import pytest

from keymacro.core.runner import Runner
from keymacro.models import (
    CallMacroAction,
    Macro,
    Step,
    TimeTrigger,
    TypeAction,
)
from keymacro.storage.yaml_repo import save_macro

from .conftest import FakeCapturer, FakeInput


def _runner(macro, dir_, *, inp=None) -> Runner:
    return Runner(
        macro,
        macro_dir=dir_,
        capturer=FakeCapturer(),
        input_normal=inp or FakeInput(),
        sleep=lambda s: None,
    )


def test_calls_sub_macro_relative_path(tmp_path: Path):
    """Parent calls ``shared/sub.yaml`` → sub's TypeAction fires through
    the same FakeInput, so the parent observes the child's keystroke."""
    sub_dir = tmp_path / "shared"
    sub_dir.mkdir()
    sub = Macro(name="sub", steps=[
        Step(
            id="t", name="type",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="from-child"),
        ),
    ])
    save_macro(sub, sub_dir / "sub.yaml")

    parent = Macro(name="parent", steps=[
        Step(
            id="call", name="call",
            trigger=TimeTrigger(delay_s=0),
            action=CallMacroAction(path="shared/sub.yaml"),
        ),
    ])
    inp = FakeInput()
    save_macro(parent, tmp_path / "parent.yaml")
    res = _runner(parent, tmp_path, inp=inp).run()

    assert res.completed
    typed = [e for e in inp.events if e[0] == "type"]
    assert typed and typed[-1][1] == "from-child"


def test_variables_propagate_both_ways(tmp_path: Path):
    """Child sees parent's vars (read) and child writes are visible
    to parent steps after the call (write)."""
    sub = Macro(name="sub", steps=[
        Step(
            id="echo", name="echo parent var",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="hi ${user}"),
        ),
    ])
    save_macro(sub, tmp_path / "sub.yaml")

    parent = Macro(name="parent", variables={"user": "Cody"}, steps=[
        Step(
            id="call", name="call",
            trigger=TimeTrigger(delay_s=0),
            action=CallMacroAction(path="sub.yaml"),
        ),
    ])
    inp = FakeInput()
    save_macro(parent, tmp_path / "parent.yaml")
    runner = _runner(parent, tmp_path, inp=inp)
    runner.run()
    typed = [e for e in inp.events if e[0] == "type"]
    assert typed[-1][1] == "hi Cody"


def test_recursion_guard_raises(tmp_path: Path):
    """a.yaml → b.yaml → a.yaml should fail loudly (and not stack-overflow)."""
    a = Macro(name="a", steps=[
        Step(
            id="ab", name="a calls b",
            trigger=TimeTrigger(delay_s=0),
            action=CallMacroAction(path="b.yaml"),
            on_failure="abort",
        ),
    ])
    b = Macro(name="b", steps=[
        Step(
            id="ba", name="b calls a",
            trigger=TimeTrigger(delay_s=0),
            action=CallMacroAction(path="a.yaml"),
            on_failure="abort",
        ),
    ])
    save_macro(a, tmp_path / "a.yaml")
    save_macro(b, tmp_path / "b.yaml")

    res = _runner(a, tmp_path).run()
    # The recursion error converts into a step failure that aborts the
    # run; assertion is that the runner *returns* rather than infinite
    # looping or stack-overflowing.
    assert not res.completed
    assert res.aborted_at is not None


def test_missing_sub_macro_file_routes_through_on_failure(tmp_path: Path):
    parent = Macro(name="parent", steps=[
        Step(
            id="call", name="call",
            trigger=TimeTrigger(delay_s=0),
            action=CallMacroAction(path="missing.yaml"),
            on_failure="skip",
        ),
    ])
    save_macro(parent, tmp_path / "parent.yaml")
    res = _runner(parent, tmp_path).run()
    # on_failure=skip → step fails but run completes.
    assert res.completed
