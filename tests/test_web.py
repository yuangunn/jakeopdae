"""Web triggers / actions: model validation, runner integration, helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pytest
from pydantic import ValidationError

from keymacro.core.runner import Runner
from keymacro.core.web import url_matches
from keymacro.models import (
    Macro,
    Step,
    TimeTrigger,
    WaitAction,
    WebClickAction,
    WebElementVisibleTrigger,
    WebNavigateAction,
    WebSessionConfig,
    WebTypeAction,
    WebUrlTrigger,
)

from .conftest import FakeCapturer, FakeInput


# --- model validation ----------------------------------------------------


def test_web_session_default_is_attach():
    cfg = WebSessionConfig()
    assert cfg.mode == "attach"
    assert cfg.cdp_endpoint == "http://localhost:9222"


def test_web_element_trigger_rejects_empty_selector():
    with pytest.raises(ValidationError):
        WebElementVisibleTrigger(selector="")


def test_web_url_trigger_modes_validate():
    WebUrlTrigger(pattern="example.com", mode="contains")
    WebUrlTrigger(pattern=r"^https://.+", mode="regex")
    WebUrlTrigger(pattern="https://example.com/", mode="exact")


def test_web_click_action_validates_selector():
    WebClickAction(selector="button.primary")
    with pytest.raises(ValidationError):
        WebClickAction(selector="")


def test_web_type_action_validates_delay():
    WebTypeAction(selector="#x", text="hi", delay_ms=50)
    with pytest.raises(ValidationError):
        WebTypeAction(selector="#x", text="hi", delay_ms=-1)


def test_web_navigate_validates_url():
    WebNavigateAction(url="https://example.com")
    with pytest.raises(ValidationError):
        WebNavigateAction(url="")


# --- url_matches helper ---------------------------------------------------


def test_url_matches_contains():
    assert url_matches("https://example.com/x", "example.com", "contains")
    assert not url_matches("https://other.com", "example.com", "contains")


def test_url_matches_exact():
    assert url_matches("  https://example.com/  ", "https://example.com/", "exact")
    assert not url_matches("https://example.com/x", "https://example.com/", "exact")


def test_url_matches_regex():
    assert url_matches("https://example.com/123", r"/\d+$", "regex")
    assert not url_matches("https://example.com/abc", r"/\d+$", "regex")


def test_url_matches_invalid_regex_returns_false():
    assert not url_matches("anything", "[invalid(", "regex")


# --- Fake web session for runner integration ------------------------------


@dataclass
class FakePage:
    current_url: str = "about:blank"
    visible_selectors: set[str] = field(default_factory=set)
    events: list[tuple] = field(default_factory=list)
    fail_state_check: bool = False

    def url(self) -> str:
        return self.current_url

    def is_element_state(self, selector: str, state: str, timeout_s: float) -> bool:
        self.events.append(("state", selector, state))
        if self.fail_state_check:
            return False
        return selector in self.visible_selectors

    def click(self, selector, *, button="left", double=False, force=False):
        self.events.append(("click", selector, button, double, force))

    def fill(self, selector, text, *, delay_ms=0):
        self.events.append(("fill", selector, text, delay_ms))

    def navigate(self, url, *, wait_until="load"):
        self.events.append(("navigate", url, wait_until))
        self.current_url = url

    def screenshot(self, path):
        self.events.append(("screenshot", path))


@dataclass
class FakeWebSession:
    page_obj: FakePage = field(default_factory=FakePage)
    started: bool = False
    stopped: bool = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def page(self):
        return self.page_obj


# --- Runner integration: triggers ----------------------------------------


def _runner_with(macro, tmp_path, web_session=None):
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=FakeInput(),
        web_session=web_session,
        sleep=lambda s: None,
    )


def test_runner_starts_web_only_when_used(tmp_path):
    web = FakeWebSession()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="x",
                trigger=TimeTrigger(delay_s=0),
                action=WaitAction(duration_s=0),
            )
        ],
    )
    runner = _runner_with(macro, tmp_path, web_session=web)
    runner.run()
    assert not web.started, "no web steps -> session must not start"


def test_web_element_trigger_succeeds_when_visible(tmp_path):
    web = FakeWebSession(page_obj=FakePage(visible_selectors={"button#go"}))
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="wait_go",
                name="버튼 대기",
                trigger=WebElementVisibleTrigger(
                    selector="button#go", timeout_s=0.5, poll_interval_s=0.05,
                ),
                action=WebClickAction(selector="button#go"),
            )
        ],
    )
    runner = _runner_with(macro, tmp_path, web_session=web)
    res = runner.run()
    assert res.completed
    assert web.started
    assert web.stopped
    kinds = [e[0] for e in web.page_obj.events]
    assert "state" in kinds
    assert "click" in kinds


def test_web_element_trigger_url_filter_blocks_match(tmp_path):
    page = FakePage(
        current_url="https://other.com/page",
        visible_selectors={"button#go"},
    )
    web = FakeWebSession(page_obj=page)
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s",
                name="x",
                trigger=WebElementVisibleTrigger(
                    selector="button#go",
                    url_contains="example.com",
                    timeout_s=0.05,
                    poll_interval_s=0.01,
                ),
                action=WebClickAction(selector="button#go"),
            )
        ],
    )
    runner = _runner_with(macro, tmp_path, web_session=web)
    res = runner.run()
    assert not res.completed, "URL filter mismatch should time out the trigger"


def test_web_url_trigger_succeeds_on_match(tmp_path):
    page = FakePage(current_url="https://example.com/lec/123/complete")
    web = FakeWebSession(page_obj=page)
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="wait_url",
                name="x",
                trigger=WebUrlTrigger(
                    pattern="/complete", mode="contains",
                    timeout_s=0.1, poll_interval_s=0.01,
                ),
                action=WaitAction(duration_s=0),
            )
        ],
    )
    runner = _runner_with(macro, tmp_path, web_session=web)
    res = runner.run()
    assert res.completed


def test_web_navigate_action_calls_page(tmp_path):
    web = FakeWebSession()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="go",
                name="x",
                trigger=TimeTrigger(delay_s=0),
                action=WebNavigateAction(url="https://example.com"),
            )
        ],
    )
    runner = _runner_with(macro, tmp_path, web_session=web)
    res = runner.run()
    assert res.completed
    nav_events = [e for e in web.page_obj.events if e[0] == "navigate"]
    assert nav_events == [("navigate", "https://example.com", "load")]


def test_web_type_action_calls_fill(tmp_path):
    web = FakeWebSession()
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="t",
                name="x",
                trigger=TimeTrigger(delay_s=0),
                action=WebTypeAction(
                    selector="input[name='username']",
                    text="alice",
                    delay_ms=10,
                ),
            )
        ],
    )
    runner = _runner_with(macro, tmp_path, web_session=web)
    runner.run()
    fills = [e for e in web.page_obj.events if e[0] == "fill"]
    assert fills == [("fill", "input[name='username']", "alice", 10)]


def test_web_session_stopped_even_on_abort(tmp_path):
    """If a web trigger times out and macro aborts, web session must still
    be cleaned up."""
    page = FakePage(visible_selectors=set())  # selector never visible
    web = FakeWebSession(page_obj=page)
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="bad",
                name="x",
                trigger=WebElementVisibleTrigger(
                    selector="#never",
                    timeout_s=0.05,
                    poll_interval_s=0.01,
                ),
                action=WaitAction(duration_s=0),
            )
        ],
    )
    runner = _runner_with(macro, tmp_path, web_session=web)
    runner.run()
    assert web.started
    assert web.stopped


def test_web_failure_capture_writes_page_screenshot(tmp_path):
    page = FakePage(visible_selectors=set())
    web = FakeWebSession(page_obj=page)
    debug_dir = tmp_path / "debug"
    macro = Macro(
        name="m",
        steps=[
            Step(
                id="bad",
                name="x",
                trigger=WebElementVisibleTrigger(
                    selector="#never",
                    timeout_s=0.05,
                    poll_interval_s=0.01,
                ),
                action=WaitAction(duration_s=0),
            )
        ],
    )
    runner = Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=FakeInput(),
        web_session=web,
        debug_capture_dir=debug_dir,
        sleep=lambda s: None,
    )
    runner.run()
    screenshots = [e for e in page.events if e[0] == "screenshot"]
    assert screenshots, "expected page.screenshot to be called on failure"


def test_macro_round_trip_preserves_web_session():
    from keymacro.storage.yaml_repo import load_macro, save_macro
    import tempfile
    from pathlib import Path

    macro = Macro(
        name="m",
        web_session=WebSessionConfig(
            mode="launch", cdp_endpoint="http://localhost:9333", headless=True,
        ),
        steps=[
            Step(
                id="s",
                name="x",
                trigger=WebUrlTrigger(pattern="example.com"),
                action=WebClickAction(selector="button"),
            )
        ],
    )
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "m.yaml"
        save_macro(macro, p)
        loaded = load_macro(p)
        assert loaded == macro
        assert loaded.web_session.mode == "launch"
