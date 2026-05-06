"""Macro.mode = 'parallel' — round-robin trigger watching.

Coverage:
    - parallel run fires the matching step's action and keeps the
      runner in the loop (no auto-abort)
    - priority decides which step wins when more than one trigger
      matches in the same poll pass
    - same priority falls back to list order
    - TimeTrigger fires only once per run (otherwise delay-0 would
      fire every cycle)
    - max_total_runtime_s caps the loop
    - stop() exits cleanly
"""

from __future__ import annotations

import threading
import time

import pytest

from keymacro.core.control import RunControl
from keymacro.core.runner import Runner
from keymacro.models import (
    ImageTrigger,
    KeyAction,
    Macro,
    PixelColorTrigger,
    Region,
    Step,
    TimeTrigger,
    TypeAction,
)

from .conftest import FakeCapturer, FakeInput, solid_bgr


def _runner(macro, tmp_path, *, inp=None, capturer=None, control=None) -> Runner:
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=capturer or FakeCapturer(),
        input_normal=inp or FakeInput(),
        control=control,
        sleep=lambda s: None,
        clock=time.monotonic,
    )


def test_parallel_fires_only_first_matching_step(tmp_path):
    """Two pixel triggers, only step B's RGB matches the framebuffer.
    Parallel run should fire B (and only B), then time out via the
    runtime cap."""
    cap = FakeCapturer(default=solid_bgr(50, 50, (0, 0, 255)))  # red
    inp = FakeInput()
    macro = Macro(
        name="m",
        mode="parallel",
        max_total_runtime_s=0.05,
        steps=[
            Step(
                id="A", name="never",
                trigger=PixelColorTrigger(
                    x=0, y=0, rgb=(0, 255, 0),  # green — never matches
                    tolerance=0,
                    timeout_s=10.0, poll_interval_s=0.01,
                ),
                action=TypeAction(text="A"),
            ),
            Step(
                id="B", name="match",
                trigger=PixelColorTrigger(
                    x=0, y=0, rgb=(255, 0, 0),  # red — matches
                    tolerance=0,
                    timeout_s=10.0, poll_interval_s=0.01,
                ),
                action=TypeAction(text="B"),
            ),
        ],
    )
    res = _runner(macro, tmp_path, inp=inp, capturer=cap).run()
    assert res.completed
    typed = [e[1] for e in inp.events if e[0] == "type"]
    assert "B" in typed
    assert "A" not in typed


def test_parallel_priority_breaks_tie(tmp_path):
    """Both pixel triggers match. Higher-priority step fires first;
    by the next cycle the runtime cap may have expired, but the
    high-priority action should land at least once before any
    low-priority action."""
    cap = FakeCapturer(default=solid_bgr(50, 50, (0, 0, 255)))
    inp = FakeInput()
    macro = Macro(
        name="m",
        mode="parallel",
        max_total_runtime_s=0.05,
        steps=[
            Step(
                id="low", name="low",
                trigger=PixelColorTrigger(
                    x=0, y=0, rgb=(255, 0, 0), tolerance=0,
                    timeout_s=10.0, poll_interval_s=0.01,
                ),
                action=TypeAction(text="low"),
                priority=0,
            ),
            Step(
                id="high", name="high",
                trigger=PixelColorTrigger(
                    x=0, y=0, rgb=(255, 0, 0), tolerance=0,
                    timeout_s=10.0, poll_interval_s=0.01,
                ),
                action=TypeAction(text="high"),
                priority=10,
            ),
        ],
    )
    res = _runner(macro, tmp_path, inp=inp, capturer=cap).run()
    assert res.completed
    typed = [e[1] for e in inp.events if e[0] == "type"]
    assert typed, "no actions ran"
    assert typed[0] == "high", f"first fire should be high-priority, got {typed[0]!r}"


def test_parallel_same_priority_uses_list_order(tmp_path):
    """Same priority → first step in list order wins each pass."""
    cap = FakeCapturer(default=solid_bgr(50, 50, (0, 0, 255)))
    inp = FakeInput()
    macro = Macro(
        name="m",
        mode="parallel",
        max_total_runtime_s=0.05,
        steps=[
            Step(
                id="first", name="f",
                trigger=PixelColorTrigger(
                    x=0, y=0, rgb=(255, 0, 0), tolerance=0,
                    timeout_s=10.0, poll_interval_s=0.01,
                ),
                action=TypeAction(text="first"),
            ),
            Step(
                id="second", name="s",
                trigger=PixelColorTrigger(
                    x=0, y=0, rgb=(255, 0, 0), tolerance=0,
                    timeout_s=10.0, poll_interval_s=0.01,
                ),
                action=TypeAction(text="second"),
            ),
        ],
    )
    res = _runner(macro, tmp_path, inp=inp, capturer=cap).run()
    typed = [e[1] for e in inp.events if e[0] == "type"]
    assert typed and typed[0] == "first"


def test_parallel_time_trigger_fires_only_once(tmp_path):
    """A TimeTrigger(delay_s=0) in parallel mode would re-match every
    cycle if we didn't gate it — verify it pulses once and stays
    quiet for the rest of the run."""
    inp = FakeInput()
    macro = Macro(
        name="m",
        mode="parallel",
        max_total_runtime_s=0.1,
        steps=[
            Step(
                id="once", name="once",
                trigger=TimeTrigger(delay_s=0.0),
                action=TypeAction(text="ping"),
            ),
        ],
    )
    res = _runner(macro, tmp_path, inp=inp).run()
    assert res.completed
    pings = [e for e in inp.events if e[0] == "type" and e[1] == "ping"]
    assert len(pings) == 1


def test_parallel_runtime_cap_exits(tmp_path):
    """No trigger ever matches — the parallel loop must still exit
    cleanly when ``max_total_runtime_s`` elapses."""
    cap = FakeCapturer(default=solid_bgr(50, 50, (0, 0, 0)))
    inp = FakeInput()
    macro = Macro(
        name="m",
        mode="parallel",
        max_total_runtime_s=0.05,
        steps=[
            Step(
                id="never", name="x",
                trigger=PixelColorTrigger(
                    x=0, y=0, rgb=(255, 255, 255), tolerance=0,
                    timeout_s=10.0, poll_interval_s=0.01,
                ),
                action=TypeAction(text="x"),
            ),
        ],
    )
    res = _runner(macro, tmp_path, inp=inp, capturer=cap).run()
    assert res.completed
    assert all(e[0] != "type" for e in inp.events)


def test_parallel_stop_request_exits(tmp_path):
    """``RunControl.stop()`` from another thread should break the
    parallel loop within a couple of poll intervals."""
    cap = FakeCapturer(default=solid_bgr(50, 50, (0, 0, 0)))
    control = RunControl()
    macro = Macro(
        name="m",
        mode="parallel",
        max_total_runtime_s=10.0,
        steps=[
            Step(
                id="never", name="x",
                trigger=PixelColorTrigger(
                    x=0, y=0, rgb=(255, 255, 255), tolerance=0,
                    timeout_s=10.0, poll_interval_s=0.01,
                ),
                action=TypeAction(text="x"),
            ),
        ],
    )
    runner = _runner(macro, tmp_path, capturer=cap, control=control)

    def stopper():
        time.sleep(0.05)
        control.stop()

    threading.Thread(target=stopper, daemon=True).start()
    started = time.monotonic()
    res = runner.run()
    elapsed = time.monotonic() - started
    # Should take ~0.05 s + a poll interval; far less than the 10 s cap.
    assert elapsed < 1.0
    assert res.completed or res.aborted_at is None
