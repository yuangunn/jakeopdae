"""Telegram notifier: payload shaping and HTTP outcome handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest

from keymacro.core.runner import RunResult, StepResult
from keymacro.notify.telegram import TelegramNotifier, build_run_summary_message


@dataclass
class FakeResponse:
    status_code: int
    text: str = ""


class FakeSession:
    def __init__(self, status: int = 200) -> None:
        self.calls: list[dict[str, Any]] = []
        self._status = status

    def post(self, url: str, json: Optional[dict] = None, timeout: Optional[float] = None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(self._status)


def test_send_posts_to_bot_api():
    sess = FakeSession()
    n = TelegramNotifier("tok", "42", session=sess)
    ok = n.send("hi")
    assert ok
    assert sess.calls[0]["url"] == "https://api.telegram.org/bottok/sendMessage"
    assert sess.calls[0]["json"]["chat_id"] == "42"
    assert sess.calls[0]["json"]["text"] == "hi"
    assert sess.calls[0]["json"]["disable_web_page_preview"] is True


def test_send_returns_false_on_non_2xx():
    sess = FakeSession(status=500)
    n = TelegramNotifier("tok", "42", session=sess)
    assert n.send("hi") is False


def test_send_swallows_session_exceptions():
    class BoomSession:
        def post(self, *a, **kw):
            raise RuntimeError("network down")
    n = TelegramNotifier("tok", "42", session=BoomSession())
    assert n.send("hi") is False


def test_constructor_rejects_empty_credentials():
    with pytest.raises(ValueError):
        TelegramNotifier("", "42")
    with pytest.raises(ValueError):
        TelegramNotifier("tok", "")


def test_build_run_summary_lists_step_outcomes():
    result = RunResult(
        macro_name="demo",
        completed=True,
        step_results=[
            StepResult("a", True, attempts=1, iterations_completed=1, duration_s=0.1),
            StepResult("b", False, error="timeout", attempts=3,
                       iterations_completed=0, duration_s=1.5),
        ],
    )
    msg = build_run_summary_message(result)
    assert "demo" in msg
    assert "completed" in msg
    assert "[OK] a" in msg
    assert "[FAIL] b" in msg
    assert "err=timeout" in msg


def test_notify_run_result_uses_session():
    sess = FakeSession()
    n = TelegramNotifier("t", "c", session=sess)
    n.notify_run_result(RunResult(macro_name="m", completed=True))
    assert len(sess.calls) == 1
    assert "completed" in sess.calls[0]["json"]["text"]
