"""C2: ClipboardChangeTrigger fires on regex-matched clipboard changes.

Test surface:
    - Baseline value never matches (no false fire on stale OTP)
    - Pattern match against new content fires + populates capture_var
    - Non-matching new content keeps polling
    - Timeout returns False so on_failure routing kicks in
"""

from __future__ import annotations

import pytest

from keymacro.core import clipboard
from keymacro.core.runner import Runner
from keymacro.models import (
    ClipboardChangeTrigger,
    Macro,
    Step,
    TypeAction,
)

from .conftest import FakeCapturer, FakeInput


class _ScriptedClipboard:
    """Backend whose ``get()`` walks through a list of values, repeating
    the last one indefinitely. Lets us script "user copies OTP at the
    third poll" scenarios deterministically."""

    def __init__(self, sequence: list[str]) -> None:
        self._seq = sequence
        self._idx = 0
        self._buf = ""

    def get(self) -> str:
        if self._idx < len(self._seq):
            v = self._seq[self._idx]
            self._idx += 1
            return v
        return self._seq[-1] if self._seq else ""

    def set(self, text: str) -> None:
        self._buf = text


@pytest.fixture
def scripted_clipboard():
    """Caller assigns ``backend.sequence``; we just install/restore."""
    original = clipboard.get_backend()

    def _install(seq: list[str]) -> _ScriptedClipboard:
        b = _ScriptedClipboard(seq)
        clipboard.set_backend(b)
        return b

    yield _install
    clipboard.set_backend(original)


def _runner(macro, tmp_path, *, inp=None) -> Runner:
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=inp or FakeInput(),
        sleep=lambda s: None,
    )


def test_baseline_doesnt_fire(tmp_path, scripted_clipboard):
    """Clipboard already has '123456' at trigger entry — that value is
    the baseline and *never* matches, even though it fits the pattern."""
    scripted_clipboard(["123456", "123456", "123456"])
    macro = Macro(name="m", steps=[
        Step(
            id="otp", name="wait",
            trigger=ClipboardChangeTrigger(
                pattern=r"\d{6}",
                capture_var="otp",
                timeout_s=0.05,
                poll_interval_s=0.01,
            ),
            action=TypeAction(text="${otp}"),
            on_failure="skip",
        ),
    ])
    inp = FakeInput()
    res = _runner(macro, tmp_path, inp=inp).run()
    # Step times out (skipped) — no type happened.
    assert res.completed
    assert all(e[0] != "type" for e in inp.events)


def test_new_content_matching_pattern_fires(tmp_path, scripted_clipboard):
    """Baseline empty, then '654321' arrives → trigger fires + variable set."""
    scripted_clipboard(["", "", "654321"])
    macro = Macro(name="m", steps=[
        Step(
            id="otp", name="wait",
            trigger=ClipboardChangeTrigger(
                pattern=r"\d{6}",
                capture_var="otp",
                timeout_s=2.0,
                poll_interval_s=0.01,
            ),
            action=TypeAction(text="${otp}"),
        ),
    ])
    inp = FakeInput()
    runner = _runner(macro, tmp_path, inp=inp)
    runner.run()
    assert runner._vars.get("otp") == "654321"
    typed = [e for e in inp.events if e[0] == "type"]
    assert typed and typed[-1][1] == "654321"


def test_non_matching_content_keeps_polling(tmp_path, scripted_clipboard):
    """User copies "hello" → not 6 digits → trigger keeps waiting until
    timeout, then fails."""
    scripted_clipboard(["", "hello", "world"])
    macro = Macro(name="m", steps=[
        Step(
            id="otp", name="wait",
            trigger=ClipboardChangeTrigger(
                pattern=r"\d{6}",
                capture_var="otp",
                timeout_s=0.05,
                poll_interval_s=0.01,
            ),
            action=TypeAction(text="${otp}"),
            on_failure="skip",
        ),
    ])
    res = _runner(macro, tmp_path).run()
    assert res.completed  # timed out, skipped


def test_extracts_match_substring(tmp_path, scripted_clipboard):
    """Pattern matches a substring inside a larger message — common
    KakaoTalk format like '인증번호 [654321] 입력하세요'."""
    scripted_clipboard(["", "인증번호 [654321] 입력해주세요"])
    macro = Macro(name="m", steps=[
        Step(
            id="otp", name="wait",
            trigger=ClipboardChangeTrigger(
                pattern=r"\d{6}",
                capture_var="otp",
                timeout_s=2.0,
                poll_interval_s=0.01,
            ),
            action=TypeAction(text="${otp}"),
        ),
    ])
    runner = _runner(macro, tmp_path)
    runner.run()
    assert runner._vars["otp"] == "654321"


def test_invalid_regex_rejected_at_model_construction():
    """Bad regex caught by Pydantic field_validator — no surprise mid-run."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        ClipboardChangeTrigger(pattern="(unclosed", capture_var="x")
