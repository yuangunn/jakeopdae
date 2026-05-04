"""Runner behaviour: trigger waits, action dispatch, branching, failure modes."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from keymacro.core.runner import Runner
from keymacro.models import (
    ClickAction,
    ImageTrigger,
    KeyAction,
    Macro,
    PixelColorTrigger,
    Region,
    Step,
    TimeTrigger,
    TypeAction,
    WaitAction,
)

from .conftest import CountingClock, FakeCapturer, FakeInput, solid_bgr, textured_bgr


def _runner(macro, tmp_path, **kwargs) -> Runner:
    """Default runner with all the test-friendly knobs wired up."""
    kwargs.setdefault("capturer", FakeCapturer())
    kwargs.setdefault("input_normal", FakeInput())
    kwargs.setdefault("sleep", lambda s: None)
    return Runner(macro, macro_dir=tmp_path, **kwargs)


def test_time_trigger_then_click(tmp_path):
    inp = FakeInput()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="wait then click",
                trigger=TimeTrigger(delay_s=0.0),
                action=ClickAction(x=10, y=20),
            )
        ],
    )
    runner = _runner(macro, tmp_path, input_normal=inp)

    res = runner.run()

    assert res.completed
    assert res.aborted_at is None
    assert ("click", 10, 20, "left", False) in inp.events


def test_image_trigger_match_drives_relative_click(tmp_path):
    template = textured_bgr(20, 20, seed=20)
    cv2.imwrite(str(tmp_path / "t.png"), template)

    # Re-read so the haystack patch matches what the runner will load.
    template_disk = cv2.imread(str(tmp_path / "t.png"), cv2.IMREAD_COLOR)
    haystack = solid_bgr(200, 200, (0, 0, 0))
    haystack[80:100, 60:80] = template_disk  # patch center at local (70, 90)
    cap = FakeCapturer(default=haystack)
    inp = FakeInput()

    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="match",
                trigger=ImageTrigger(
                    template="t.png",
                    region=Region(x=0, y=0, w=200, h=200),
                    confidence=0.85,
                    timeout_s=1.0,
                    multi_scale=False,
                ),
                action=ClickAction(relative_to_match=True, x=5, y=-3),
            )
        ],
    )
    runner = _runner(macro, tmp_path, capturer=cap, input_normal=inp)

    res = runner.run()

    assert res.completed
    # Center (70, 90) + offset (5, -3).
    evt = inp.events[0]
    assert evt[0] == "click"
    assert abs(evt[1] - 75) <= 1
    assert abs(evt[2] - 87) <= 1


def test_image_trigger_timeout_aborts(tmp_path):
    template = textured_bgr(10, 10, seed=30)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    haystack = textured_bgr(50, 50, seed=31)  # different texture, no occurrence

    cap = FakeCapturer(default=haystack)
    inp = FakeInput()

    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="never",
                trigger=ImageTrigger(
                    template="t.png",
                    region=Region(x=0, y=0, w=50, h=50),
                    confidence=0.99,
                    timeout_s=0.05,
                    poll_interval_s=0.01,
                    multi_scale=False,
                ),
                action=ClickAction(x=0, y=0),
            )
        ],
    )
    runner = _runner(macro, tmp_path, capturer=cap, input_normal=inp)

    res = runner.run()

    assert not res.completed
    assert res.aborted_at == "s1"
    # Action must NOT have fired.
    assert not any(e[0] == "click" for e in inp.events)


def test_branching_via_on_success_goto(tmp_path):
    inp = FakeInput()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="first",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=1, y=1),
                on_success_goto="s3",
            ),
            Step(
                id="s2", name="skipped",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=99, y=99),
            ),
            Step(
                id="s3", name="third",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=3, y=3),
            ),
        ],
    )
    runner = _runner(macro, tmp_path, input_normal=inp)

    res = runner.run()

    clicks = [e for e in inp.events if e[0] == "click"]
    assert res.completed
    assert clicks == [
        ("click", 1, 1, "left", False),
        ("click", 3, 3, "left", False),
    ]


def test_skip_on_failure_advances_to_next_step(tmp_path):
    template = textured_bgr(10, 10, seed=40)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    haystack = textured_bgr(50, 50, seed=41)  # template not present
    cap = FakeCapturer(default=haystack)
    inp = FakeInput()

    macro = Macro(
        name="m",
        steps=[
            Step(
                id="bad", name="will timeout",
                trigger=ImageTrigger(
                    template="t.png",
                    region=Region(x=0, y=0, w=50, h=50),
                    confidence=0.99,
                    timeout_s=0.02,
                    poll_interval_s=0.01,
                    multi_scale=False,
                ),
                action=ClickAction(x=0, y=0),
                on_failure="skip",
            ),
            Step(
                id="ok", name="continues",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=99, y=99),
            ),
        ],
    )
    runner = _runner(macro, tmp_path, capturer=cap, input_normal=inp)

    res = runner.run()

    assert res.completed
    assert ("click", 99, 99, "left", False) in inp.events


def test_retry_succeeds_after_first_failure(tmp_path):
    """Runner attempts retry_count + 1 times when on_failure='retry'."""
    template = textured_bgr(10, 10, seed=50)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    template_disk = cv2.imread(str(tmp_path / "t.png"), cv2.IMREAD_COLOR)

    miss = textured_bgr(50, 50, seed=51)  # no template here
    hit = solid_bgr(50, 50, (0, 0, 0))
    hit[20:30, 20:30] = template_disk

    # First grab returns "miss" (causes first attempt to time out), then "hit".
    cap = FakeCapturer(frames=[miss, hit, hit, hit, hit, hit])
    cap.default = hit  # backstop
    inp = FakeInput()

    macro = Macro(
        name="m",
        steps=[
            Step(
                id="r", name="retry",
                trigger=ImageTrigger(
                    template="t.png",
                    region=Region(x=0, y=0, w=50, h=50),
                    confidence=0.85,
                    timeout_s=0.0,           # one probe per attempt
                    poll_interval_s=0.01,
                    multi_scale=False,
                ),
                action=ClickAction(x=0, y=0),
                on_failure="retry",
                retry_count=2,
            )
        ],
    )
    runner = _runner(macro, tmp_path, capturer=cap, input_normal=inp)

    res = runner.run()

    assert res.completed
    assert res.step_results[0].attempts >= 2


def test_max_total_runtime_aborts(tmp_path):
    macro = Macro(
        name="m",
        max_total_runtime_s=0.0,
        steps=[
            Step(
                id="s1", name="first",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=1, y=1),
            )
        ],
    )
    clock = CountingClock(start=0.0, step=1.0)
    runner = _runner(macro, tmp_path, clock=clock)

    res = runner.run()

    # run_start = 0.0, next clock() in loop check returns 1.0 > 0.0 -> abort.
    assert not res.completed
    assert res.aborted_at == "s1"


def test_pixel_color_trigger_fires(tmp_path):
    pixel = np.array([[[100, 50, 200]]], dtype=np.uint8)  # BGR
    cap = FakeCapturer(default=pixel)
    inp = FakeInput()

    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="red-ish pixel",
                trigger=PixelColorTrigger(
                    x=10, y=10, rgb=(200, 50, 100), tolerance=5,
                    timeout_s=0.1, poll_interval_s=0.01,
                ),
                action=ClickAction(x=42, y=42),
            )
        ],
    )
    runner = _runner(macro, tmp_path, capturer=cap, input_normal=inp)

    res = runner.run()

    assert res.completed
    assert ("click", 42, 42, "left", False) in inp.events


def test_stop_flag_halts_runner(tmp_path):
    class TripOnce:
        def __init__(self):
            self.calls = 0

        def is_set(self) -> bool:
            self.calls += 1
            return self.calls > 1  # let the first check pass; trip after that

    inp = FakeInput()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="long wait",
                trigger=TimeTrigger(delay_s=10.0),
                action=ClickAction(x=1, y=1),
            )
        ],
    )
    runner = _runner(macro, tmp_path, input_normal=inp, stop_flag=TripOnce())

    res = runner.run()

    assert not res.completed
    # Action must not have fired.
    assert not any(e[0] == "click" for e in inp.events)


def test_key_and_type_actions(tmp_path):
    inp = FakeInput()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="k", name="press enter",
                trigger=TimeTrigger(delay_s=0),
                action=KeyAction(keys="enter"),
            ),
            Step(
                id="t", name="type hi",
                trigger=TimeTrigger(delay_s=0),
                action=TypeAction(text="hi"),
            ),
            Step(
                id="w", name="wait",
                trigger=TimeTrigger(delay_s=0),
                action=WaitAction(duration_s=0),
            ),
        ],
    )
    runner = _runner(macro, tmp_path, input_normal=inp)

    res = runner.run()

    assert res.completed
    kinds = [e[0] for e in inp.events]
    assert "key" in kinds
    assert "type" in kinds


def test_unknown_goto_target_raises(tmp_path):
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="x",
                trigger=TimeTrigger(delay_s=0),
                action=WaitAction(duration_s=0),
                on_success_goto="does-not-exist",
            )
        ],
    )
    runner = _runner(macro, tmp_path)

    with pytest.raises(ValueError):
        runner.run()


def test_empty_macro_completes_immediately(tmp_path):
    macro = Macro(name="m", steps=[])
    runner = _runner(macro, tmp_path)

    res = runner.run()

    assert res.completed
    assert res.step_results == []
