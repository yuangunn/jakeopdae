"""C1: TypeAction.mode='auto' uses clipboard paste for non-ASCII text.

Korean text via raw keystrokes typically loses jamo composition or
mojibakes through whichever IME is active. Pasting via the OS
clipboard (which runs through the IME's paste path) preserves the
codepoints intact.

We stub the clipboard backend so the test doesn't touch the real one,
and use FakeInput to capture the expected ``ctrl+v`` keystroke.
"""

from __future__ import annotations

import pytest

from keymacro.core import clipboard
from keymacro.core.runner import Runner
from keymacro.models import Macro, Step, TimeTrigger, TypeAction

from .conftest import FakeCapturer, FakeInput


class _MemBackend:
    def __init__(self) -> None:
        self._buf = ""

    def get(self) -> str:
        return self._buf

    def set(self, text: str) -> None:
        self._buf = text


@pytest.fixture
def stub_clipboard():
    original = clipboard.get_backend()
    fake = _MemBackend()
    clipboard.set_backend(fake)
    try:
        yield fake
    finally:
        clipboard.set_backend(original)


def _runner(macro, tmp_path, *, inp) -> Runner:
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=inp,
        sleep=lambda s: None,
    )


def test_ascii_uses_keystrokes(tmp_path, stub_clipboard):
    """Pure ASCII goes through the keyboard backend — clipboard
    untouched."""
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="ascii",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="hello world", mode="auto"),
        ),
    ])
    _runner(macro, tmp_path, inp=inp).run()
    typed = [e for e in inp.events if e[0] == "type"]
    assert typed and typed[-1][1] == "hello world"
    keys = [e for e in inp.events if e[0] == "key"]
    assert ("key", "ctrl+v") not in keys


def test_korean_falls_back_to_clipboard_paste(tmp_path, stub_clipboard):
    """Non-ASCII triggers the clipboard-paste path and the OS clipboard
    receives the text verbatim."""
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="hangul",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="안녕하세요", mode="auto"),
        ),
    ])
    _runner(macro, tmp_path, inp=inp).run()
    # No raw type call — used clipboard path.
    typed = [e for e in inp.events if e[0] == "type"]
    assert not typed
    keys = [e for e in inp.events if e[0] == "key"]
    assert ("key", "ctrl+v") in keys


def test_explicit_keystrokes_mode_overrides_for_korean(tmp_path, stub_clipboard):
    """``mode='keystrokes'`` always uses the keyboard backend even
    for Korean — for terminals / ssh sessions that ignore paste."""
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="forced",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="안녕", mode="keystrokes"),
        ),
    ])
    _runner(macro, tmp_path, inp=inp).run()
    typed = [e for e in inp.events if e[0] == "type"]
    assert typed and typed[-1][1] == "안녕"


def test_explicit_clipboard_mode_for_ascii(tmp_path, stub_clipboard):
    """``mode='clipboard'`` forces paste for ASCII text too."""
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="forced-paste",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="abc", mode="clipboard"),
        ),
    ])
    _runner(macro, tmp_path, inp=inp).run()
    keys = [e for e in inp.events if e[0] == "key"]
    assert ("key", "ctrl+v") in keys


def test_clipboard_restored_after_paste(tmp_path, stub_clipboard):
    """The user's pre-existing clipboard contents survive the paste."""
    stub_clipboard.set("user's prior content")
    inp = FakeInput()
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="hangul",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="안녕", mode="auto"),
        ),
    ])
    _runner(macro, tmp_path, inp=inp).run()
    assert stub_clipboard.get() == "user's prior content"


def test_unavailable_clipboard_falls_back_to_keystrokes(tmp_path):
    """If the clipboard backend errors, raw typing happens as a last
    resort — better than no input at all."""

    class _BoomBackend:
        def get(self) -> str:
            raise clipboard.ClipboardUnavailable("none")

        def set(self, text: str) -> None:
            raise clipboard.ClipboardUnavailable("none")

    original = clipboard.get_backend()
    clipboard.set_backend(_BoomBackend())
    try:
        inp = FakeInput()
        macro = Macro(name="m", steps=[
            Step(
                id="s1", name="hangul",
                trigger=TimeTrigger(delay_s=0),
                action=TypeAction(text="안녕", mode="auto"),
            ),
        ])
        _runner(macro, tmp_path, inp=inp).run()
        typed = [e for e in inp.events if e[0] == "type"]
        assert typed and typed[-1][1] == "안녕"
    finally:
        clipboard.set_backend(original)
