"""Web-aware trigger / action / session models.

These extend the macro vocabulary from "look at pixels, click coordinates"
to "look at the live DOM of an attached Chrome, click semantic UI elements".
The runner picks them up only when ``[web]`` extra (Playwright) is
installed; without it, the models still validate and serialise so YAML
files remain portable across environments.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# --- session config ------------------------------------------------------------


class WebSessionConfig(BaseModel):
    """Per-macro browser configuration.

    ``attach`` connects to a Chrome already started with
    ``--remote-debugging-port=<port>``. ``launch`` spins up Playwright's
    own Chromium binary; useful when the macro doesn't depend on the
    user's existing cookies / login state.
    """

    mode: Literal["attach", "launch"] = "attach"
    cdp_endpoint: str = "http://localhost:9222"
    browser_channel: str = "chrome"
    headless: bool = False
    new_page: bool = False
    """For attach mode: open a fresh tab instead of using the active one."""

    @field_validator("cdp_endpoint")
    @classmethod
    def _endpoint_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("cdp_endpoint must not be empty")
        return v


# --- triggers -----------------------------------------------------------------


class WebElementVisibleTrigger(BaseModel):
    """Wait for an element matching ``selector`` to become visible.

    ``selector`` is whatever Playwright understands — CSS
    (``button.primary``), text (``text=다음``), role
    (``role=button[name="다음"]``), or XPath (``xpath=//button``). When
    ``url_contains`` is set, the trigger only succeeds if the active
    tab's URL also contains the substring.
    """

    type: Literal["web_element"] = "web_element"
    selector: str
    url_contains: Optional[str] = None
    state: Literal["visible", "attached", "hidden", "detached"] = "visible"
    timeout_s: float = 10.0
    poll_interval_s: float = 0.3

    @field_validator("selector")
    @classmethod
    def _selector_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("selector must not be empty")
        return v

    @field_validator("timeout_s", "poll_interval_s")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("must be >= 0")
        return v


class WebUrlTrigger(BaseModel):
    """Wait until the active tab's URL matches.

    ``mode='contains'`` does a substring match; ``'regex'`` does a
    regex search; ``'exact'`` requires equality (after normalisation).
    """

    type: Literal["web_url"] = "web_url"
    pattern: str
    mode: Literal["contains", "regex", "exact"] = "contains"
    timeout_s: float = 10.0
    poll_interval_s: float = 0.3

    @field_validator("pattern")
    @classmethod
    def _pattern_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("pattern must not be empty")
        return v


# --- actions ------------------------------------------------------------------


class WebClickAction(BaseModel):
    """Click a DOM element by selector."""

    type: Literal["web_click"] = "web_click"
    selector: str
    button: Literal["left", "right", "middle"] = "left"
    double: bool = False
    force: bool = False
    """Bypass actionability checks (use sparingly — usually means a
    layout bug in the page, but sometimes necessary on stubborn elements)."""

    @field_validator("selector")
    @classmethod
    def _selector_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("selector must not be empty")
        return v


class WebTypeAction(BaseModel):
    """Fill an input element with text. Replaces existing value."""

    type: Literal["web_type"] = "web_type"
    selector: str
    text: str
    delay_ms: int = 0
    """Per-keystroke delay; 0 = paste-style instant fill."""

    @field_validator("selector")
    @classmethod
    def _selector_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("selector must not be empty")
        return v

    @field_validator("delay_ms")
    @classmethod
    def _delay_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("delay_ms must be >= 0")
        return v


class WebNavigateAction(BaseModel):
    """Navigate the active tab to ``url``."""

    type: Literal["web_navigate"] = "web_navigate"
    url: str
    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load"

    @field_validator("url")
    @classmethod
    def _url_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url must not be empty")
        return v
