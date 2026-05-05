"""HttpAction runner integration.

Stubs ``keymacro.core.http_client._REQUEST`` so the test suite never
hits the network. Tests verify:
    - URL/headers/body are passed through
    - ${var} substitution applies to URL, headers, body
    - response body lands in store_in variable
    - HTTP error converts to step error → on_failure routing
"""

from __future__ import annotations

import pytest

from keymacro.core import http_client
from keymacro.core.runner import Runner
from keymacro.models import (
    HttpAction,
    Macro,
    Step,
    TimeTrigger,
    TypeAction,
)

from .conftest import FakeCapturer, FakeInput


@pytest.fixture
def http_log():
    """Replace the network backend with a recorder. Yields a list of
    ``(method, url, headers, body, timeout_s)`` tuples + a configurable
    response."""
    log: list[tuple] = []
    response = {"text": "ok"}

    def fake_request(method, url, *, headers, body, timeout_s):
        log.append((method, url, dict(headers), body, timeout_s))
        return response["text"]

    original = http_client._REQUEST
    http_client._REQUEST = fake_request
    try:
        yield log, response
    finally:
        http_client._REQUEST = original


def _runner(macro, tmp_path) -> Runner:
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=FakeInput(),
        sleep=lambda s: None,
    )


def test_http_get_passes_through(tmp_path, http_log):
    log, _ = http_log
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="ping",
            trigger=TimeTrigger(delay_s=0),
            action=HttpAction(url="https://api.example.com/health"),
        ),
    ])
    _runner(macro, tmp_path).run()
    assert len(log) == 1
    method, url, headers, body, timeout = log[0]
    assert method == "GET"
    assert url == "https://api.example.com/health"
    assert body == ""
    assert timeout == 10.0


def test_http_post_with_substitution(tmp_path, http_log):
    log, _ = http_log
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="post",
            trigger=TimeTrigger(delay_s=0),
            action=HttpAction(
                url="https://hooks.example.com/${slug}",
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer ${token}",
                },
                body='{"otp":"${otp}"}',
            ),
        ),
    ])
    runner = _runner(macro, tmp_path)
    runner._vars.update({
        "slug": "training-done",
        "token": "secret123",
        "otp": "654321",
    })
    runner.run()
    method, url, headers, body, _ = log[0]
    assert method == "POST"
    assert url == "https://hooks.example.com/training-done"
    assert headers["Authorization"] == "Bearer secret123"
    assert body == '{"otp":"654321"}'


def test_http_response_stored_in_variable(tmp_path, http_log):
    log, response = http_log
    response["text"] = "echo: ok"
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="hit",
            trigger=TimeTrigger(delay_s=0),
            action=HttpAction(url="https://x", store_in="reply"),
        ),
        Step(
            id="s2", name="use",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="got: ${reply}"),
        ),
    ])
    inp = FakeInput()
    runner = Runner(
        macro, macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=inp,
        sleep=lambda s: None,
    )
    runner.run()
    assert runner._vars["reply"] == "echo: ok"
    typed = [e for e in inp.events if e[0] == "type"]
    assert typed[-1][1] == "got: echo: ok"


def test_http_error_routes_through_on_failure(tmp_path):
    """HttpError bubbles up as a step error so ``on_failure='skip'``
    can swallow it without crashing the run."""
    def boom(*args, **kwargs):
        raise http_client.HttpError("HTTP 500 Server Error", status=500)

    original = http_client._REQUEST
    http_client._REQUEST = boom
    try:
        macro = Macro(name="m", steps=[
            Step(
                id="s1", name="failing",
                trigger=TimeTrigger(delay_s=0),
                action=HttpAction(url="https://x"),
                on_failure="skip",
            ),
        ])
        res = Runner(
            macro, macro_dir=tmp_path,
            capturer=FakeCapturer(), input_normal=FakeInput(),
            sleep=lambda s: None,
        ).run()
        assert res.completed
    finally:
        http_client._REQUEST = original
