"""Validation rules on the Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from keymacro.models import (
    ClickAction,
    ImageTrigger,
    KeyAction,
    Macro,
    PixelColorTrigger,
    Region,
    Step,
    TimeTrigger,
    WaitAction,
)


def test_region_rejects_zero_size():
    with pytest.raises(ValidationError):
        Region(x=0, y=0, w=0, h=10)
    with pytest.raises(ValidationError):
        Region(x=0, y=0, w=10, h=-1)


def test_image_trigger_confidence_bounds():
    region = Region(x=0, y=0, w=10, h=10)
    ImageTrigger(template="t.png", region=region, confidence=0.5)
    ImageTrigger(template="t.png", region=region, confidence=1.0)
    with pytest.raises(ValidationError):
        ImageTrigger(template="t.png", region=region, confidence=0.0)
    with pytest.raises(ValidationError):
        ImageTrigger(template="t.png", region=region, confidence=1.1)


def test_image_trigger_rejects_negative_timeouts():
    region = Region(x=0, y=0, w=10, h=10)
    with pytest.raises(ValidationError):
        ImageTrigger(template="t.png", region=region, timeout_s=-1)
    with pytest.raises(ValidationError):
        ImageTrigger(template="t.png", region=region, poll_interval_s=-0.1)


def test_time_trigger_non_negative():
    TimeTrigger(delay_s=0.0)
    TimeTrigger(delay_s=2.5)
    with pytest.raises(ValidationError):
        TimeTrigger(delay_s=-1)


def test_pixel_trigger_rgb_range():
    PixelColorTrigger(x=0, y=0, rgb=(0, 0, 0))
    PixelColorTrigger(x=0, y=0, rgb=(255, 255, 255))
    with pytest.raises(ValidationError):
        PixelColorTrigger(x=0, y=0, rgb=(256, 0, 0))
    with pytest.raises(ValidationError):
        PixelColorTrigger(x=0, y=0, rgb=(-1, 0, 0))


def test_key_action_rejects_empty_keys():
    KeyAction(keys="enter")
    with pytest.raises(ValidationError):
        KeyAction(keys="")
    with pytest.raises(ValidationError):
        KeyAction(keys="   ")


def test_step_rejects_empty_id():
    with pytest.raises(ValidationError):
        Step(
            id=" ",
            name="x",
            trigger=TimeTrigger(delay_s=0),
            action=WaitAction(duration_s=0),
        )


def test_step_rejects_negative_retry():
    with pytest.raises(ValidationError):
        Step(
            id="a",
            name="x",
            trigger=TimeTrigger(delay_s=0),
            action=WaitAction(duration_s=0),
            retry_count=-1,
        )


def test_macro_unique_step_ids():
    s1 = Step(
        id="a", name="A",
        trigger=TimeTrigger(delay_s=0),
        action=WaitAction(duration_s=0),
    )
    s2 = Step(
        id="a", name="dup",
        trigger=TimeTrigger(delay_s=0),
        action=WaitAction(duration_s=0),
    )
    with pytest.raises(ValidationError):
        Macro(name="m", steps=[s1, s2])


def test_macro_round_trip_preserves_data():
    s = Step(
        id="step1",
        name="Test",
        trigger=ImageTrigger(
            template="x.png", region=Region(x=0, y=0, w=10, h=10)
        ),
        action=ClickAction(x=100, y=100, double=True),
    )
    m = Macro(name="hello", steps=[s])
    data = m.model_dump(mode="json")
    m2 = Macro.model_validate(data)
    assert m2 == m


def test_macro_step_by_id():
    s = Step(
        id="lookup",
        name="x",
        trigger=TimeTrigger(delay_s=0),
        action=WaitAction(duration_s=0),
    )
    m = Macro(name="m", steps=[s])
    assert m.step_by_id("lookup") is s
    with pytest.raises(KeyError):
        m.step_by_id("nope")


def test_discriminated_union_picks_right_subclass():
    """The discriminated unions on Trigger/Action must round-trip via dicts."""
    raw = {
        "id": "x",
        "name": "n",
        "trigger": {"type": "time", "delay_s": 1.0},
        "action": {"type": "click", "x": 5, "y": 6},
    }
    s = Step.model_validate(raw)
    assert isinstance(s.trigger, TimeTrigger)
    assert isinstance(s.action, ClickAction)
