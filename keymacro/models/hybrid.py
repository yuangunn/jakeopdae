"""HybridImageTrigger — image match with a non-CDP browser-URL guard.

The cheap-and-cheerful middle ground between purely-pixel
:class:`ImageTrigger` and CDP-driven :class:`WebElementVisibleTrigger`:
it still matches a screen template (so the user's *regular* Chrome
works — no debug port needed), but only fires when the active browser
tab's URL also matches a substring or pattern. The URL is read through
the OS accessibility API in :mod:`keymacro.core.browser_url`, not
through CDP, so it works on any unmodified browser.

When ``uiautomation`` isn't installed the URL guard degrades to window-
title matching, which is good enough for substring checks against
stable site names.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .trigger import Region


class HybridImageTrigger(BaseModel):
    """Pixel-template match plus a browser-URL guard (no CDP).

    Behaves like :class:`ImageTrigger` for matching, then adds an extra
    pre-condition: the active tab's URL must satisfy ``url_contains``
    under ``url_mode``. When the URL guard fails, the trigger does *not*
    capture the screen — it just polls the URL until either the URL
    matches (then it tries the image match) or the timeout elapses.

    ``browser`` lets the user pin the URL read to a particular browser
    family if they keep multiple kinds open (e.g. Edge for work, Chrome
    for browsing); the default ``"any"`` reads from whichever Chromium
    or Firefox window is found first.
    """

    type: Literal["hybrid_image"] = "hybrid_image"
    template: str
    region: Region

    # URL guard
    url_contains: str
    url_mode: Literal["contains", "regex", "exact"] = "contains"
    browser: Literal["chrome", "edge", "firefox", "any"] = "any"

    # Image-match knobs (mirrors ImageTrigger)
    confidence: float = 0.9
    timeout_s: float = 10.0
    poll_interval_s: float = 0.3
    multi_scale: bool = True
    scale_min: float = 0.9
    scale_max: float = 1.1
    scale_steps: int = 5

    @field_validator("template", "url_contains")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            raise ValueError("confidence must be in (0, 1]")
        return v

    @field_validator("timeout_s", "poll_interval_s")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("must be >= 0")
        return v

    @field_validator("scale_steps")
    @classmethod
    def _steps_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("scale_steps must be >= 1")
        return v
