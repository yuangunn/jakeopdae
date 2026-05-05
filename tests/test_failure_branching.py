"""B5: ``on_failure_goto`` enables if/else step branching.

The pattern: a "watch for image X" step that, on success, jumps to a
"already done" branch via ``on_success_goto``; on failure (X never
appeared), jumps to a "do X then continue" branch via ``on_failure_goto``.
"""

from __future__ import annotations

import pytest

from keymacro.core.runner import Runner
from keymacro.models import (
    KeyAction,
    Macro,
    Step,
    TimeTrigger,
    PixelColorTrigger,
    TypeAction,
)

from .conftest import FakeCapturer, FakeInput, solid_bgr


def _runner(macro, tmp_path, *, inp=None, capturer=None) -> Runner:
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=capturer or FakeCapturer(),
        input_normal=inp or FakeInput(),
        sleep=lambda s: None,
    )


def test_on_failure_goto_branches_to_else(tmp_path):
    """Step 'check' fails (pixel never matches), branches to 'fallback'."""
    # Pixel trigger that times out fast — capturer returns black, the
    # trigger is looking for white.
    cap = FakeCapturer(default=solid_bgr(50, 50, (0, 0, 0)))
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="check", name="if",
            trigger=PixelColorTrigger(
                x=10, y=10, rgb=(0, 0, 255),  # never matches
                tolerance=0, timeout_s=0.05, poll_interval_s=0.01,
            ),
            action=KeyAction(keys="enter"),
            on_failure_goto="fallback",
        ),
        Step(
            id="dont_run", name="should be skipped",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="WRONG"),
        ),
        Step(
            id="fallback", name="else branch",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="took fallback"),
        ),
    ])
    res = _runner(macro, tmp_path, inp=inp, capturer=cap).run()
    assert res.completed
    typed = [e for e in inp.events if e[0] == "type"]
    # Only the fallback ran — the in-between step was skipped over.
    assert typed == [("type", "took fallback", 0.0)]


def test_on_failure_goto_overrides_on_failure_abort(tmp_path):
    """Even with ``on_failure='abort'``, an explicit ``on_failure_goto``
    wins — branching takes precedence over the default policy."""
    cap = FakeCapturer(default=solid_bgr(50, 50, (0, 0, 0)))
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="check", name="check",
            trigger=PixelColorTrigger(
                x=10, y=10, rgb=(0, 0, 255),
                tolerance=0, timeout_s=0.05, poll_interval_s=0.01,
            ),
            action=KeyAction(keys="enter"),
            on_failure="abort",  # would abort without the goto
            on_failure_goto="next",
        ),
        Step(
            id="next", name="next",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="continued"),
        ),
    ])
    res = _runner(macro, tmp_path, inp=inp, capturer=cap).run()
    assert res.completed
    typed = [e for e in inp.events if e[0] == "type"]
    assert typed == [("type", "continued", 0.0)]


def test_dangling_on_failure_goto_raises_at_run_start(tmp_path):
    """Pre-flight inside the runner catches dangling targets so a
    typo doesn't fail mid-run after side effects."""
    macro = Macro(name="m", steps=[
        Step(
            id="check", name="x",
            trigger=TimeTrigger(delay_s=0),
            action=KeyAction(keys="enter"),
            on_failure_goto="ghost_step",
        ),
    ])
    with pytest.raises(ValueError, match="on_failure_goto"):
        _runner(macro, tmp_path).run()
