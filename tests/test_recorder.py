"""Recorder event → Step conversion."""

from __future__ import annotations

from keymacro.core.recorder import RecordedEvent, events_to_macro, events_to_steps
from keymacro.models import (
    ClickAction,
    KeyAction,
    Macro,
    TimeTrigger,
    TypeAction,
)


def _ev(kind, t, **payload):
    return RecordedEvent(kind=kind, t=t, payload=payload)


def test_consecutive_chars_become_one_type_action():
    events = [
        _ev("char", 0.10, char="h"),
        _ev("char", 0.15, char="i"),
        _ev("char", 0.20, char=" "),
        _ev("char", 0.30, char="!"),
    ]
    steps = events_to_steps(events)
    assert len(steps) == 1
    assert isinstance(steps[0].action, TypeAction)
    assert steps[0].action.text == "hi !"


def test_long_pause_splits_type_actions():
    events = [
        _ev("char", 0.10, char="a"),
        _ev("char", 0.15, char="b"),
        # 1s gap exceeds the 0.5s default
        _ev("char", 1.20, char="c"),
        _ev("char", 1.25, char="d"),
    ]
    steps = events_to_steps(events)
    type_actions = [s.action for s in steps if isinstance(s.action, TypeAction)]
    assert [a.text for a in type_actions] == ["ab", "cd"]


def test_click_then_type_then_click():
    events = [
        _ev("click", 0.50, x=10, y=20, button="left"),
        _ev("char", 0.80, char="x"),
        _ev("click", 1.50, x=30, y=40, button="left"),
    ]
    steps = events_to_steps(events)
    kinds = [type(s.action).__name__ for s in steps]
    assert kinds == ["ClickAction", "TypeAction", "ClickAction"]
    assert steps[1].action.text == "x"


def test_double_click_collapses_to_one_step():
    events = [
        _ev("click", 1.00, x=50, y=50, button="left"),
        _ev("click", 1.10, x=50, y=50, button="left"),  # within double-click window
    ]
    steps = events_to_steps(events)
    assert len(steps) == 1
    assert isinstance(steps[0].action, ClickAction)
    assert steps[0].action.double is True


def test_two_separate_clicks_at_same_spot_stay_separate():
    events = [
        _ev("click", 1.00, x=50, y=50, button="left"),
        # 1s gap > double-click window
        _ev("click", 2.50, x=50, y=50, button="left"),
    ]
    steps = events_to_steps(events)
    assert len(steps) == 2
    assert all(isinstance(s.action, ClickAction) for s in steps)
    assert all(s.action.double is False for s in steps)


def test_special_keys_become_key_actions():
    events = [
        _ev("key", 0.20, key="enter"),
        _ev("key", 0.50, key="tab"),
    ]
    steps = events_to_steps(events)
    assert len(steps) == 2
    assert all(isinstance(s.action, KeyAction) for s in steps)
    assert steps[0].action.keys == "enter"


def test_wait_uses_gap_to_previous_step():
    events = [
        _ev("click", 1.00, x=10, y=20, button="left"),
        _ev("click", 3.50, x=30, y=40, button="left"),
    ]
    steps = events_to_steps(events)
    # First step waits ~1s (its own t), second step waits ~2.5s (gap from first).
    assert isinstance(steps[0].trigger, TimeTrigger)
    assert isinstance(steps[1].trigger, TimeTrigger)
    assert abs(steps[0].trigger.delay_s - 1.0) < 0.05
    assert abs(steps[1].trigger.delay_s - 2.5) < 0.05


def test_clamp_to_min_delay():
    events = [
        _ev("click", 0.001, x=0, y=0, button="left"),
        _ev("click", 0.002, x=10, y=10, button="left"),
    ]
    steps = events_to_steps(events, min_delay_s=0.05)
    # Both should be clamped to at least 0.05s
    assert all(s.trigger.delay_s >= 0.05 for s in steps)


def test_events_to_macro_preserves_step_count():
    events = [
        _ev("click", 0.50, x=10, y=20, button="left"),
        _ev("char", 0.70, char="a"),
        _ev("char", 0.75, char="b"),
        _ev("key", 1.20, key="enter"),
    ]
    macro = events_to_macro(events, name="test-rec")
    assert isinstance(macro, Macro)
    assert macro.name == "test-rec"
    assert len(macro.steps) == 3   # click + type("ab") + key(enter)


def test_unique_step_ids_after_recording():
    """Conversion must keep step ids unique even on long sessions."""
    events = []
    for i in range(50):
        events.append(_ev("click", 0.1 * i, x=i, y=i, button="left"))
    steps = events_to_steps(events)
    ids = [s.id for s in steps]
    assert len(ids) == len(set(ids))


def test_empty_events_yields_empty_steps():
    assert events_to_steps([]) == []


def test_buffered_chars_flushed_at_end():
    """Trailing typed text without a follow-up event must still be a step."""
    events = [
        _ev("char", 0.10, char="a"),
        _ev("char", 0.20, char="b"),
    ]
    steps = events_to_steps(events)
    assert len(steps) == 1
    assert steps[0].action.text == "ab"
