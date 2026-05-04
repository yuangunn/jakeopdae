"""Run history store + observer integration."""

from __future__ import annotations

import time

import pytest

from keymacro.core.runner import Runner
from keymacro.history import HistoryStore
from keymacro.models import (
    ClickAction,
    Macro,
    Step,
    TimeTrigger,
    WaitAction,
)

from .conftest import FakeCapturer, FakeInput


def test_in_memory_round_trip():
    store = HistoryStore(":memory:")
    run = store.begin_run("macroA")
    s1 = store.begin_step(run, "s1")
    store.end_step(s1, success=True)
    s2 = store.begin_step(run, "s2")
    store.end_step(s2, success=False, error="timeout")
    store.end_run(run, completed=False, aborted_at="s2")

    runs = store.list_recent_runs()
    assert len(runs) == 1
    assert runs[0]["macro_name"] == "macroA"
    assert runs[0]["num_steps"] == 2
    assert runs[0]["num_succeeded"] == 1
    assert runs[0]["num_failed"] == 1
    assert runs[0]["completed"] == 0


def test_stats_for_macro():
    store = HistoryStore(":memory:")
    for completed in (True, True, False, True):
        run = store.begin_run("trainer")
        s = store.begin_step(run, "s1")
        store.end_step(s, success=completed)
        store.end_run(run, completed=completed, aborted_at=None if completed else "s1")
        time.sleep(0.001)

    stats = store.stats_for_macro("trainer")
    assert stats["total"] == 4
    assert stats["completed"] == 3
    assert stats["success_rate"] == 0.75
    assert stats["last_run_at"] is not None


def test_observer_records_run_lifecycle(tmp_path):
    store = HistoryStore(":memory:")
    inp = FakeInput()
    macro = Macro(
        name="M", steps=[
            Step(
                id="a", name="x",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=1, y=1),
            ),
            Step(
                id="b", name="y",
                trigger=TimeTrigger(delay_s=0),
                action=WaitAction(duration_s=0),
            ),
        ],
    )

    Runner(
        macro, macro_dir=tmp_path,
        capturer=FakeCapturer(), input_normal=inp,
        observer=store.observer(),
        sleep=lambda s: None,
    ).run()

    runs = store.list_recent_runs()
    assert len(runs) == 1
    assert runs[0]["macro_name"] == "M"
    assert runs[0]["num_steps"] == 2
    assert runs[0]["num_succeeded"] == 2
    assert runs[0]["completed"] == 1


def test_observer_handles_aborted_run(tmp_path):
    """When a step times out and the macro aborts, the row should still
    show that step as failed."""
    import cv2
    from .conftest import textured_bgr
    from keymacro.models import ImageTrigger, Region

    template = textured_bgr(10, 10, seed=1)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    haystack = textured_bgr(40, 40, seed=2)

    store = HistoryStore(":memory:")
    macro = Macro(
        name="aborts", steps=[
            Step(
                id="bad", name="never",
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
    Runner(
        macro, macro_dir=tmp_path,
        capturer=FakeCapturer(default=haystack), input_normal=FakeInput(),
        observer=store.observer(),
        sleep=lambda s: None,
    ).run()

    runs = store.list_recent_runs()
    assert len(runs) == 1
    assert runs[0]["completed"] == 0
    assert runs[0]["aborted_at"] == "bad"
    assert runs[0]["num_failed"] == 1


def test_steps_for_run():
    store = HistoryStore(":memory:")
    run = store.begin_run("x")
    s1 = store.begin_step(run, "first")
    store.end_step(s1, success=True)
    s2 = store.begin_step(run, "second")
    store.end_step(s2, success=False, error="oh no")
    store.end_run(run, completed=False, aborted_at="second")

    rows = store.steps_for_run(run)
    assert [r["step_id"] for r in rows] == ["first", "second"]
    assert rows[1]["error"] == "oh no"
