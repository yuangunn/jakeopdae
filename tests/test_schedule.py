"""ScheduleTrigger validation + ``seconds_until_next`` math."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from keymacro.models import ScheduleTrigger
from keymacro.models.schedule import seconds_until_next


def test_at_format_validation():
    ScheduleTrigger(at="09:00")
    ScheduleTrigger(at="23:59")
    ScheduleTrigger(at="0:0")  # gets normalised
    with pytest.raises(ValidationError):
        ScheduleTrigger(at="9am")
    with pytest.raises(ValidationError):
        ScheduleTrigger(at="24:00")
    with pytest.raises(ValidationError):
        ScheduleTrigger(at="9:60")


def test_at_normalised_to_zero_padded():
    t = ScheduleTrigger(at="9:5")
    assert t.at == "09:05"


def test_weekdays_validation():
    ScheduleTrigger(at="09:00", weekdays=[0, 1, 2, 3, 4])
    ScheduleTrigger(at="09:00", weekdays=[6])
    with pytest.raises(ValidationError):
        ScheduleTrigger(at="09:00", weekdays=[])
    with pytest.raises(ValidationError):
        ScheduleTrigger(at="09:00", weekdays=[7])
    with pytest.raises(ValidationError):
        ScheduleTrigger(at="09:00", weekdays=[-1])


def test_weekdays_dedup_and_sort():
    t = ScheduleTrigger(at="09:00", weekdays=[3, 0, 0, 1])
    assert t.weekdays == [0, 1, 3]


# --- seconds_until_next math --------------------------------------------


def test_today_slot_in_future_returns_seconds_to_today():
    # Wednesday 8:00am, target 9:00am same day, weekday allowed.
    now = datetime(2026, 5, 6, 8, 0, 0)  # Wed
    s = seconds_until_next("09:00", [0, 1, 2, 3, 4], now=now)
    assert s == 3600  # 1 hour


def test_today_slot_already_passed_rolls_to_next_allowed_day():
    # Wednesday 10:00am, target 9:00am, weekdays Mon-Fri.
    now = datetime(2026, 5, 6, 10, 0, 0)  # Wed
    s = seconds_until_next("09:00", [0, 1, 2, 3, 4], now=now)
    # Next match: Thursday 9:00am = 23 hours later.
    assert s == 23 * 3600


def test_friday_evening_skips_to_monday_when_no_weekend():
    # Friday 18:00, target 09:00 weekdays only.
    now = datetime(2026, 5, 8, 18, 0, 0)  # Fri
    s = seconds_until_next("09:00", [0, 1, 2, 3, 4], now=now)
    # Sat skipped, Sun skipped, Mon 09:00 = 63 hours later.
    assert s == 63 * 3600


def test_today_slot_now_returns_tomorrow():
    """Edge case: scheduled time is *exactly* now — the candidate is
    not strictly in the future (``<= now`` check), so we roll to the
    next allowed day."""
    now = datetime(2026, 5, 6, 9, 0, 0)  # Wed exactly 9am
    s = seconds_until_next("09:00", [0, 1, 2, 3, 4], now=now)
    assert s == 24 * 3600


def test_works_for_single_weekday():
    # Wednesday → next Sunday at 12:00 (weekdays=[6])
    now = datetime(2026, 5, 6, 0, 0, 0)  # Wed midnight
    s = seconds_until_next("12:00", [6], now=now)
    # Wed→Sun = 4 days, plus 12 hours.
    assert s == 4 * 86400 + 12 * 3600


def test_round_trip_via_yaml(tmp_path):
    from keymacro.models import Macro, Step, WaitAction
    from keymacro.storage.yaml_repo import load_macro, save_macro

    m = Macro(
        name="m",
        steps=[
            Step(
                id="s", name="9am",
                trigger=ScheduleTrigger(at="09:00", weekdays=[0, 1, 2, 3, 4]),
                action=WaitAction(duration_s=0),
            )
        ],
    )
    p = tmp_path / "m.yaml"
    save_macro(m, p)
    loaded = load_macro(p)
    assert loaded == m
    assert loaded.steps[0].trigger.at == "09:00"
