"""ClipboardAction runner integration + clipboard helper.

Stubs the platform clipboard backend so the test suite doesn't touch
the real system clipboard (which would race with anything the user
copied to it during the test).
"""

from __future__ import annotations

import pytest

from keymacro.core import clipboard
from keymacro.core.runner import Runner
from keymacro.models import (
    ClipboardAction,
    Macro,
    Step,
    TimeTrigger,
    TypeAction,
)

from .conftest import FakeCapturer, FakeInput


class _MemBackend:
    """In-memory clipboard backend used to stub the real OS one in tests."""

    def __init__(self) -> None:
        self._buf = ""

    def get(self) -> str:
        return self._buf

    def set(self, text: str) -> None:
        self._buf = text


@pytest.fixture(autouse=True)
def _stub_clipboard():
    """Replace the auto-selected platform backend with the in-memory
    one for every test in this module — restores after each test so
    other suites that use the real clipboard (none today) aren't
    affected."""
    original = clipboard.get_backend()
    fake = _MemBackend()
    clipboard.set_backend(fake)
    try:
        yield fake
    finally:
        clipboard.set_backend(original)


def _runner(macro, tmp_path, *, inp=None) -> Runner:
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=inp or FakeInput(),
        sleep=lambda s: None,
    )


def test_clipboard_set_writes_to_backend(tmp_path, _stub_clipboard):
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="set",
            trigger=TimeTrigger(delay_s=0),
            action=ClipboardAction(op="set", text="안녕하세요"),
        ),
    ])
    res = _runner(macro, tmp_path).run()
    assert res.completed
    assert _stub_clipboard.get() == "안녕하세요"


def test_clipboard_set_substitutes_variables(tmp_path, _stub_clipboard):
    """${var} placeholders in the text should expand at run time."""
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="set",
            trigger=TimeTrigger(delay_s=0),
            action=ClipboardAction(op="set", text="hello ${name}"),
        ),
    ])
    runner = _runner(macro, tmp_path)
    runner._vars["name"] = "world"
    runner.run()
    assert _stub_clipboard.get() == "hello world"


def test_clipboard_paste_sends_ctrl_v(tmp_path, _stub_clipboard):
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="paste",
            trigger=TimeTrigger(delay_s=0),
            action=ClipboardAction(op="paste"),
        ),
    ])
    _runner(macro, tmp_path, inp=inp).run()
    # FakeInput records ("key", "ctrl+v") for the keystroke.
    assert ("key", "ctrl+v") in inp.events


def test_clipboard_copy_captures_into_variable(tmp_path, _stub_clipboard):
    """``op='copy'`` should send Ctrl+C *and* read whatever the OS
    clipboard contains afterwards into the named variable so the next
    step can use ``${variable}``.

    We pre-load the stub backend with text to simulate the OS having
    accepted the Ctrl+C.
    """
    _stub_clipboard.set("OTP-998877")
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="copy",
            trigger=TimeTrigger(delay_s=0),
            action=ClipboardAction(op="copy", variable="captured"),
        ),
        Step(
            id="s2", name="use",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="${captured}"),
        ),
    ])
    runner = _runner(macro, tmp_path, inp=inp)
    runner.run()

    # Step 1 sent Ctrl+C, then read backend → variable
    assert ("key", "ctrl+c") in inp.events
    assert runner._vars["captured"] == "OTP-998877"
    # Step 2 typed the variable's resolved value
    typed = [e for e in inp.events if e[0] == "type"]
    assert typed and typed[-1][1] == "OTP-998877"


def test_clipboard_unavailable_propagates_as_step_error(tmp_path):
    """When the clipboard backend raises, the runner converts it into
    a step error — on_failure=skip routes don't crash the whole run."""

    class _BoomBackend:
        def get(self) -> str:
            raise clipboard.ClipboardUnavailable("no xclip")

        def set(self, text: str) -> None:
            raise clipboard.ClipboardUnavailable("no xclip")

    clipboard.set_backend(_BoomBackend())
    try:
        macro = Macro(name="m", steps=[
            Step(
                id="s1", name="set",
                trigger=TimeTrigger(delay_s=0),
                action=ClipboardAction(op="set", text="x"),
                on_failure="skip",
            ),
        ])
        res = _runner(macro, tmp_path).run()
        # on_failure=skip means the step fails but the run completes.
        assert res.completed
    finally:
        # Reset to the in-memory stub for the next test.
        clipboard.set_backend(_MemBackend())
