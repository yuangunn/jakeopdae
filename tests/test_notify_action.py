"""C3: NotifyAction sends one-line messages through a webhook channel.

Stubs ``keymacro.notify.channels._POST`` so tests don't need network.
"""

from __future__ import annotations

import json

import pytest

from keymacro.core.runner import Runner
from keymacro.notify import channels
from keymacro.models import (
    Macro,
    NotifyAction,
    Step,
    TimeTrigger,
)

from .conftest import FakeCapturer, FakeInput


@pytest.fixture
def post_log():
    """Replace channels._POST with a recorder + tunable status."""
    log: list[tuple] = []

    def fake_post(url, *, headers, body, timeout_s):
        log.append((url, dict(headers), body, timeout_s))
        return ""

    original = channels._POST
    channels._POST = fake_post
    try:
        yield log
    finally:
        channels._POST = original


def _runner(macro, tmp_path) -> Runner:
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=FakeInput(),
        sleep=lambda s: None,
    )


def test_telegram_provider_hits_bot_api(tmp_path, post_log):
    macro = Macro(name="m", steps=[
        Step(
            id="n", name="ping",
            trigger=TimeTrigger(delay_s=0),
            action=NotifyAction(
                provider="telegram",
                token="abc",
                chat_id="-100",
                text="작업 완료",
            ),
        ),
    ])
    _runner(macro, tmp_path).run()
    url, headers, body, _ = post_log[0]
    assert url == "https://api.telegram.org/botabc/sendMessage"
    payload = json.loads(body)
    assert payload["chat_id"] == "-100"
    assert payload["text"] == "작업 완료"


def test_slack_provider_uses_text_field(tmp_path, post_log):
    macro = Macro(name="m", steps=[
        Step(
            id="n", name="slack",
            trigger=TimeTrigger(delay_s=0),
            action=NotifyAction(
                provider="slack",
                webhook_url="https://hooks.slack.com/services/X",
                text="hello",
            ),
        ),
    ])
    _runner(macro, tmp_path).run()
    url, _, body, _ = post_log[0]
    assert url == "https://hooks.slack.com/services/X"
    assert json.loads(body)["text"] == "hello"


def test_discord_provider_uses_content_field(tmp_path, post_log):
    """Discord webhooks need ``content`` not ``text`` — verify the
    payload re-shaping happens."""
    macro = Macro(name="m", steps=[
        Step(
            id="n", name="discord",
            trigger=TimeTrigger(delay_s=0),
            action=NotifyAction(
                provider="discord",
                webhook_url="https://discord.com/api/webhooks/X",
                text="hello",
            ),
        ),
    ])
    _runner(macro, tmp_path).run()
    body = post_log[0][2]
    payload = json.loads(body)
    assert "content" in payload
    assert payload["content"] == "hello"
    assert "text" not in payload


def test_kakao_work_provider(tmp_path, post_log):
    macro = Macro(name="m", steps=[
        Step(
            id="n", name="kw",
            trigger=TimeTrigger(delay_s=0),
            action=NotifyAction(
                provider="kakao_work",
                webhook_url="https://workhook.example.com/abc",
                text="완료",
            ),
        ),
    ])
    _runner(macro, tmp_path).run()
    body = post_log[0][2]
    assert json.loads(body)["text"] == "완료"


def test_variable_substitution_in_text(tmp_path, post_log):
    macro = Macro(name="m", steps=[
        Step(
            id="n", name="ping",
            trigger=TimeTrigger(delay_s=0),
            action=NotifyAction(
                provider="telegram",
                token="abc",
                chat_id="42",
                text="OTP는 ${otp} 입니다",
            ),
        ),
    ])
    runner = _runner(macro, tmp_path)
    runner._vars["otp"] = "654321"
    runner.run()
    body = post_log[0][2]
    assert json.loads(body)["text"] == "OTP는 654321 입니다"


def test_notify_error_routes_through_on_failure(tmp_path):
    """NotifyError converts to step error → on_failure handling."""

    def boom(*args, **kwargs):
        raise channels.NotifyError("HTTP 500")

    original = channels._POST
    channels._POST = boom
    try:
        macro = Macro(name="m", steps=[
            Step(
                id="n", name="failing",
                trigger=TimeTrigger(delay_s=0),
                action=NotifyAction(
                    provider="slack",
                    webhook_url="https://x",
                    text="hi",
                ),
                on_failure="skip",
            ),
        ])
        res = _runner(macro, tmp_path).run()
        assert res.completed
    finally:
        channels._POST = original


def test_telegram_missing_credentials_fails_loudly():
    """Empty token/chat_id from a YAML edit shouldn't silently no-op."""
    with pytest.raises(channels.NotifyError):
        channels.send_telegram(token="", chat_id="42", text="x")
    with pytest.raises(channels.NotifyError):
        channels.send_telegram(token="abc", chat_id="", text="x")


def test_slack_missing_webhook_fails_loudly():
    with pytest.raises(channels.NotifyError):
        channels.send_slack(webhook_url="", text="x")
