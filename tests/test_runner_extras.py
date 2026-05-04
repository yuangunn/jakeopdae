"""Phase 2/3/5 runner additions: pause via Control, repeat, observer hooks,
failure capture."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from keymacro.core.control import RunControl
from keymacro.core.matcher import MatchResult
from keymacro.core.runner import Runner
from keymacro.models import (
    ClickAction,
    ImageTrigger,
    Macro,
    Region,
    Step,
    TimeTrigger,
    WaitAction,
)

from .conftest import FakeCapturer, FakeInput, solid_bgr, textured_bgr


# --- repeat ---------------------------------------------------------------


def test_repeat_runs_action_n_times(tmp_path):
    inp = FakeInput()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="repeat 4 clicks",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=1, y=2),
                repeat=4,
            )
        ],
    )
    runner = Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=inp,
        sleep=lambda s: None,
    )
    res = runner.run()

    clicks = [e for e in inp.events if e[0] == "click"]
    assert res.completed
    assert len(clicks) == 4
    assert res.step_results[0].iterations_completed == 4


def test_repeat_with_failure_aborts_after_first_failed_iteration(tmp_path):
    template = textured_bgr(10, 10, seed=7)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    haystack = textured_bgr(40, 40, seed=8)  # template not present
    cap = FakeCapturer(default=haystack)
    inp = FakeInput()

    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="repeat with image trigger that times out",
                trigger=ImageTrigger(
                    template="t.png",
                    region=Region(x=0, y=0, w=40, h=40),
                    confidence=0.99,
                    timeout_s=0.0,
                    poll_interval_s=0.01,
                    multi_scale=False,
                ),
                action=ClickAction(x=0, y=0),
                repeat=5,
                on_failure="abort",
            )
        ],
    )
    runner = Runner(
        macro, macro_dir=tmp_path,
        capturer=cap, input_normal=inp,
        sleep=lambda s: None,
    )
    res = runner.run()

    assert not res.completed
    # Iteration 0 fails; should not have any click events.
    assert not any(e[0] == "click" for e in inp.events)
    assert res.step_results[0].iterations_completed == 0


# --- observer -------------------------------------------------------------


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def on_run_start(self, name):
        self.events.append(("run_start", name))

    def on_step_start(self, step_id, attempt, iteration):
        self.events.append(("step_start", step_id, attempt, iteration))

    def on_match_attempt(self, step_id, score, found):
        self.events.append(("match", step_id, round(score, 2), found))

    def on_step_end(self, step_id, success, match, error):
        self.events.append(("step_end", step_id, success, error))

    def on_failure_capture(self, step_id, image):
        self.events.append(("failure_capture", step_id, image.shape))

    def on_run_end(self, completed, aborted_at):
        self.events.append(("run_end", completed, aborted_at))


def test_observer_receives_run_lifecycle(tmp_path):
    obs = RecordingObserver()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="x",
                trigger=TimeTrigger(delay_s=0),
                action=WaitAction(duration_s=0),
            )
        ],
    )
    runner = Runner(
        macro, macro_dir=tmp_path,
        capturer=FakeCapturer(), input_normal=FakeInput(),
        observer=obs, sleep=lambda s: None,
    )
    runner.run()

    kinds = [e[0] for e in obs.events]
    assert kinds[0] == "run_start"
    assert "step_start" in kinds
    assert "step_end" in kinds
    assert kinds[-1] == "run_end"


def test_observer_receives_match_scores(tmp_path):
    template = textured_bgr(10, 10, seed=9)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    template_disk = cv2.imread(str(tmp_path / "t.png"), cv2.IMREAD_COLOR)
    haystack = solid_bgr(40, 40, (0, 0, 0))
    haystack[10:20, 10:20] = template_disk
    cap = FakeCapturer(default=haystack)

    obs = RecordingObserver()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="image",
                trigger=ImageTrigger(
                    template="t.png",
                    region=Region(x=0, y=0, w=40, h=40),
                    confidence=0.85,
                    timeout_s=0.5,
                    poll_interval_s=0.01,
                    multi_scale=False,
                ),
                action=ClickAction(x=0, y=0),
            )
        ],
    )
    runner = Runner(
        macro, macro_dir=tmp_path,
        capturer=cap, input_normal=FakeInput(),
        observer=obs, sleep=lambda s: None,
    )
    runner.run()

    matches = [e for e in obs.events if e[0] == "match"]
    assert matches
    last = matches[-1]
    assert last[3] is True  # found


# --- failure capture ------------------------------------------------------


def test_failure_capture_writes_png(tmp_path):
    template = textured_bgr(10, 10, seed=11)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    haystack = textured_bgr(40, 40, seed=12)
    cap = FakeCapturer(default=haystack)

    debug_dir = tmp_path / "debug"
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="never", name="x",
                trigger=ImageTrigger(
                    template="t.png",
                    region=Region(x=0, y=0, w=40, h=40),
                    confidence=0.99,
                    timeout_s=0.0,
                    poll_interval_s=0.01,
                    multi_scale=False,
                ),
                action=ClickAction(x=0, y=0),
            )
        ],
    )
    runner = Runner(
        macro, macro_dir=tmp_path,
        capturer=cap, input_normal=FakeInput(),
        debug_capture_dir=debug_dir,
        sleep=lambda s: None,
    )
    runner.run()

    pngs = list(debug_dir.glob("*never*.png"))
    assert pngs, "expected failure capture PNG to be written"


# --- pause via control ---------------------------------------------------


def test_pause_is_visible_in_runner_via_control(tmp_path):
    """A control that goes paused-then-stopped should not run any actions
    after the stop."""

    class PauseThenStop:
        def __init__(self) -> None:
            self.checks = 0
            self._stopped = False
            self._paused = False

        def is_paused(self) -> bool:
            self.checks += 1
            # First time: pretend we're paused. After 2 checks: stop.
            if self.checks <= 1:
                return False
            if self.checks == 2:
                self._paused = True
                return True
            self._stopped = True
            return False

        def is_stopped(self) -> bool:
            return self._stopped

    control = PauseThenStop()
    inp = FakeInput()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="long wait",
                trigger=TimeTrigger(delay_s=0.5),
                action=ClickAction(x=1, y=1),
            )
        ],
    )
    runner = Runner(
        macro, macro_dir=tmp_path,
        capturer=FakeCapturer(), input_normal=inp,
        control=control, sleep=lambda s: None,
    )
    res = runner.run()

    assert not res.completed
    assert not any(e[0] == "click" for e in inp.events)
