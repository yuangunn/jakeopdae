"""Schedule (calendar / clock) trigger.

Fires when the wall clock crosses a configured ``HH:MM`` on one of the
allowed weekdays. Designed for the "run this macro every weekday at 9am"
use case — uses local timezone and sleeps long stretches efficiently
without spinning the CPU.

For cron-level expressiveness (multiple times per day, exact minute
ranges, etc.) chain ScheduleTriggers in different steps.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# 0 = Monday, 6 = Sunday (Python ``date.weekday()`` convention).
ALL_WEEKDAYS: list[int] = [0, 1, 2, 3, 4, 5, 6]


class ScheduleTrigger(BaseModel):
    """Wait until the next occurrence of ``at`` on an allowed weekday.

    Examples (YAML):

    .. code-block:: yaml

        # Every weekday at 09:00
        trigger:
          type: schedule
          at: "09:00"
          weekdays: [0, 1, 2, 3, 4]   # Mon..Fri

        # Sunday afternoons
        trigger:
          type: schedule
          at: "14:30"
          weekdays: [6]
    """

    type: Literal["schedule"] = "schedule"
    at: str
    """``HH:MM`` (24-hour). Local timezone."""
    weekdays: list[int] = Field(default_factory=lambda: list(ALL_WEEKDAYS))
    """0 = Monday … 6 = Sunday. Default: every day."""
    grace_s: float = 60.0
    """If the scheduled time was within ``grace_s`` seconds in the past
    when polling started, fire immediately rather than waiting until
    tomorrow — protects against being a few seconds late after a
    GHA/cron spawn."""

    @field_validator("at")
    @classmethod
    def _at_format(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("at must be HH:MM (24-hour)")
        try:
            h, m = int(parts[0]), int(parts[1])
        except ValueError as e:
            raise ValueError("at must be HH:MM (24-hour)") from e
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("HH must be 0..23 and MM must be 0..59")
        return f"{h:02d}:{m:02d}"

    @field_validator("weekdays")
    @classmethod
    def _weekdays_range(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("weekdays must include at least one day")
        for d in v:
            if d not in range(7):
                raise ValueError("weekdays must be in 0..6 (0=Mon, 6=Sun)")
        return sorted(set(v))

    @field_validator("grace_s")
    @classmethod
    def _grace_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("grace_s must be >= 0")
        return v


# --- helpers shared with the runner (kept here to be unit-testable) ----------


def seconds_until_next(at: str, weekdays: list[int], *, now=None) -> float:
    """Return the number of seconds from ``now`` until the next match.

    ``now`` defaults to ``datetime.now()``; pass an explicit value in
    tests so behaviour is deterministic.
    """
    from datetime import datetime, timedelta

    now = now or datetime.now()
    h, m = (int(x) for x in at.split(":"))
    weekdays = sorted(set(weekdays))

    # Try today, then each subsequent day up to 7 days out.
    for offset in range(0, 8):
        candidate = (now + timedelta(days=offset)).replace(
            hour=h, minute=m, second=0, microsecond=0,
        )
        if offset == 0 and candidate <= now:
            # Today's slot already passed — skip.
            continue
        if candidate.weekday() not in weekdays:
            continue
        return (candidate - now).total_seconds()
    # Should never reach here (every weekday is in the 7-day window).
    return 0.0
