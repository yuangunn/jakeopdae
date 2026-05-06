"""Macro.humanization — anti-bot-detection jitter on time / click / type.

Verify the runner samples jitter from the configured ranges and that
zero settings = original deterministic behaviour.
"""

from __future__ import annotations

import time

import pytest

from keymacro.core.runner import Runner
from keymacro.models import (
    ClickAction,
    HumanizationConfig,
    KeyAction,
    Macro,
    Step,
    TimeTrigger,
    TypeAction,
)

from .conftest import FakeCapturer, FakeInput


def _runner(macro, tmp_path, *, inp=None, sleep_log=None) -> Runner:
    sleep_fn = lambda s: sleep_log.append(s) if sleep_log is not None else None
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=inp or FakeInput(),
        sleep=sleep_fn,
        clock=time.monotonic,
    )


def test_zero_humanization_keeps_deterministic_behaviour(tmp_path):
    """Default config (all zero) → click coords reach the backend
    unchanged."""
    inp = FakeInput()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="x",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=100, y=200),
            ),
        ],
    )
    _runner(macro, tmp_path, inp=inp).run()
    clicks = [e for e in inp.events if e[0] == "click"]
    assert clicks == [("click", 100, 200, "left", False)]


def test_click_position_jitter_within_range(tmp_path):
    """With ``click_position_px=3`` every click should land inside
    ``±3`` of the requested coordinate. We run the action many times
    and assert (a) every offset is in range and (b) at least one
    sample isn't dead-on (proving jitter is actually firing)."""
    inp = FakeInput()
    macro = Macro(
        name="m",
        humanization=HumanizationConfig(click_position_px=3),
        steps=[
            Step(
                id="s1", name="x",
                trigger=TimeTrigger(delay_s=0),
                action=ClickAction(x=500, y=500),
                repeat=80,
            ),
        ],
    )
    _runner(macro, tmp_path, inp=inp).run()
    xs = [e[1] for e in inp.events if e[0] == "click"]
    ys = [e[2] for e in inp.events if e[0] == "click"]
    assert len(xs) == 80
    for x in xs:
        assert 497 <= x <= 503, f"click x out of jitter range: {x}"
    for y in ys:
        assert 497 <= y <= 503
    # Statistical sanity: with 80 samples and ±3 jitter, > 95 %
    # chance at least one differs from the centre.
    assert len(set(xs)) > 1 or len(set(ys)) > 1


def test_time_jitter_perturbs_sleep_durations(tmp_path):
    """``time_jitter_pct=20`` ± 20 % → at least one sleep call's
    duration should differ from the requested value."""
    sleep_log: list[float] = []
    macro = Macro(
        name="m",
        humanization=HumanizationConfig(time_jitter_pct=20.0),
        steps=[
            Step(
                id="s1", name="wait",
                trigger=TimeTrigger(delay_s=0.1),
                action=KeyAction(keys="enter"),
                repeat=20,
            ),
        ],
    )
    _runner(macro, tmp_path, sleep_log=sleep_log).run()
    # We can't assert exact values, but with 20 iterations and ±20 %
    # jitter the probability of all 20 samples landing on exactly
    # 0.05 (the chunk size) is essentially zero. Look for any
    # variation across all sleep calls.
    chunks = [s for s in sleep_log if s > 0]
    assert chunks, "no sleep recorded"
    assert len(set(round(s, 4) for s in chunks)) > 1, (
        "all sleep durations identical — jitter not firing"
    )


def test_humanization_is_active_predicate():
    cfg = HumanizationConfig()
    assert not cfg.is_active
    assert HumanizationConfig(click_position_px=2).is_active
    assert HumanizationConfig(time_jitter_pct=5).is_active
    assert HumanizationConfig(type_interval_jitter_pct=10).is_active


def test_humanization_validators():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        HumanizationConfig(time_jitter_pct=200)
    with pytest.raises(pydantic.ValidationError):
        HumanizationConfig(click_position_px=999)
    with pytest.raises(pydantic.ValidationError):
        HumanizationConfig(time_jitter_pct=-5)
