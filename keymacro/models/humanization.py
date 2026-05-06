"""Humanization (anti-bot-detection) settings for a Macro.

Many sites that the user wants to automate flag perfectly-rhythmic,
pixel-perfect input as bot traffic. Real human input has small
amounts of jitter — clicks land within a few pixels of the target,
and typing / waiting durations vary by tens of percent.

This module models that variability as percent-and-pixel knobs the
user can dial in from the GUI. The runner applies them at action
dispatch time:

    - ``time_jitter_pct``: every ``_interruptible_sleep`` is randomly
      multiplied by ``1 ± (pct / 100)``. 0 means "no jitter" (default
      behaviour); 5 means "± 5 %"; 100 means "0× to 2×".
    - ``click_position_px``: ClickAction's ``(x, y)`` gets a uniform
      random offset within ``[-px, +px]`` on each axis before the
      backend dispatches the click. 0 means dead-on.
    - ``type_interval_jitter_pct``: TypeAction's per-character
      ``interval_s`` gets the same percentage jitter as time waits.

All knobs are *additive* and zero by default, so existing macros
behave identically until the user opts in.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class HumanizationConfig(BaseModel):
    """Per-macro anti-bot-detection knobs. All zero = original
    deterministic behaviour."""

    time_jitter_pct: float = 0.0
    """Percent jitter applied to every interruptible sleep. The
    actual wait becomes ``base * (1 + uniform(-pct/100, +pct/100))``.
    Typical "subtle" value: 5–15. Above 50 starts noticeably
    breaking timing-sensitive macros."""

    click_position_px: int = 0
    """Maximum pixel offset added to ``ClickAction(x, y)`` on each
    axis. Each click samples a fresh uniform offset in
    ``[-px, +px]``. Typical "subtle" value: 1–3. Big enough to
    break pixel-perfect bot detection, small enough that the click
    still lands on a button."""

    type_interval_jitter_pct: float = 0.0
    """Per-character typing interval jitter. Same shape as
    ``time_jitter_pct`` but applied to ``TypeAction.interval_s``.
    Real typists vary their inter-key timing by ±20–40 %."""

    @field_validator("time_jitter_pct", "type_interval_jitter_pct")
    @classmethod
    def _pct_range(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError("jitter percent must be 0..100")
        return v

    @field_validator("click_position_px")
    @classmethod
    def _px_range(cls, v: int) -> int:
        if v < 0 or v > 50:
            raise ValueError("click position jitter must be 0..50 px")
        return v

    @property
    def is_active(self) -> bool:
        """``True`` if any knob is non-zero — runner uses this to
        skip the random-sampling overhead when humanization is off."""
        return (
            self.time_jitter_pct > 0
            or self.click_position_px > 0
            or self.type_interval_jitter_pct > 0
        )
