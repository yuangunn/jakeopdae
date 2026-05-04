"""OCR trigger + ExtractText action + macro variables."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from keymacro.core.runner import Runner
from keymacro.core.variables import referenced_names, substitute
from keymacro.models import (
    ExtractTextAction,
    Macro,
    OcrTextTrigger,
    Region,
    Step,
    TimeTrigger,
    TypeAction,
    WaitAction,
    WebNavigateAction,
)

from .conftest import FakeCapturer, FakeInput


# --- variable substitution helper ---------------------------------------


def test_substitute_replaces_known_vars():
    out = substitute("hi ${name}", {"name": "alice"})
    assert out == "hi alice"


def test_substitute_keeps_unknown_vars_intact():
    out = substitute("hi ${nope}", {"name": "alice"})
    assert out == "hi ${nope}"


def test_substitute_handles_no_vars_fast_path():
    assert substitute("plain text", {"a": "b"}) == "plain text"


def test_substitute_multiple_refs():
    out = substitute("${a}-${b}-${a}", {"a": "X", "b": "Y"})
    assert out == "X-Y-X"


def test_substitute_strict_name_pattern():
    """Only ``[A-Za-z_][A-Za-z0-9_]*`` style names are recognised; spaces
    or hyphens leave the placeholder alone."""
    assert substitute("${ no spaces}", {"no spaces": "x"}) == "${ no spaces}"


def test_referenced_names_finds_all_refs():
    assert referenced_names("${a} and ${b}") == {"a", "b"}
    assert referenced_names("plain") == set()


# --- model validation ---------------------------------------------------


def test_ocr_trigger_rejects_empty_text():
    with pytest.raises(ValidationError):
        OcrTextTrigger(region=Region(x=0, y=0, w=10, h=10), text="")


def test_extract_text_rejects_invalid_variable():
    with pytest.raises(ValidationError):
        ExtractTextAction(
            region=Region(x=0, y=0, w=10, h=10),
            variable="has space",
        )
    with pytest.raises(ValidationError):
        ExtractTextAction(
            region=Region(x=0, y=0, w=10, h=10),
            variable="has-hyphen",
        )
    # Underscores are fine
    ExtractTextAction(
        region=Region(x=0, y=0, w=10, h=10),
        variable="snake_case_OK",
    )


# --- runner: OCR trigger ------------------------------------------------


def _macro_with(*steps, variables=None):
    return Macro(
        name="m",
        steps=list(steps),
        variables=variables or {},
    )


def test_ocr_trigger_fires_when_text_matches(tmp_path):
    macro = _macro_with(
        Step(
            id="s1", name="x",
            trigger=OcrTextTrigger(
                region=Region(x=0, y=0, w=100, h=100),
                text="다음", timeout_s=0.2, poll_interval_s=0.01,
            ),
            action=WaitAction(duration_s=0),
        )
    )
    with patch(
        "keymacro.core.runner.ocr_read_text",
        return_value="이전  다음  완료",
    ):
        runner = Runner(
            macro, macro_dir=tmp_path,
            capturer=FakeCapturer(), input_normal=FakeInput(),
            sleep=lambda s: None,
        )
        res = runner.run()
    assert res.completed


def test_ocr_trigger_times_out_when_text_absent(tmp_path):
    macro = _macro_with(
        Step(
            id="s1", name="x",
            trigger=OcrTextTrigger(
                region=Region(x=0, y=0, w=100, h=100),
                text="never_appears", timeout_s=0.05, poll_interval_s=0.01,
            ),
            action=WaitAction(duration_s=0),
        )
    )
    with patch(
        "keymacro.core.runner.ocr_read_text",
        return_value="something else entirely",
    ):
        runner = Runner(
            macro, macro_dir=tmp_path,
            capturer=FakeCapturer(), input_normal=FakeInput(),
            sleep=lambda s: None,
        )
        res = runner.run()
    assert not res.completed


def test_ocr_trigger_case_insensitive_by_default(tmp_path):
    macro = _macro_with(
        Step(
            id="s1", name="x",
            trigger=OcrTextTrigger(
                region=Region(x=0, y=0, w=10, h=10),
                text="SUBMIT", timeout_s=0.2, poll_interval_s=0.01,
            ),
            action=WaitAction(duration_s=0),
        )
    )
    with patch("keymacro.core.runner.ocr_read_text", return_value="please submit now"):
        runner = Runner(macro, macro_dir=tmp_path,
                        capturer=FakeCapturer(), input_normal=FakeInput(),
                        sleep=lambda s: None)
        res = runner.run()
    assert res.completed


def test_ocr_trigger_regex_mode(tmp_path):
    macro = _macro_with(
        Step(
            id="s1", name="x",
            trigger=OcrTextTrigger(
                region=Region(x=0, y=0, w=10, h=10),
                text=r"\d{6}", mode="regex",
                timeout_s=0.2, poll_interval_s=0.01,
            ),
            action=WaitAction(duration_s=0),
        )
    )
    with patch("keymacro.core.runner.ocr_read_text", return_value="OTP: 123456 expires"):
        runner = Runner(macro, macro_dir=tmp_path,
                        capturer=FakeCapturer(), input_normal=FakeInput(),
                        sleep=lambda s: None)
        res = runner.run()
    assert res.completed


# --- runner: ExtractText writes variable + TypeAction substitutes -------


def test_extract_text_then_type_substitutes(tmp_path):
    inp = FakeInput()
    macro = _macro_with(
        Step(
            id="extract", name="ocr",
            trigger=TimeTrigger(delay_s=0),
            action=ExtractTextAction(
                region=Region(x=0, y=0, w=200, h=50),
                variable="otp",
            ),
        ),
        Step(
            id="type", name="paste",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="OTP=${otp}"),
        ),
    )
    with patch("keymacro.core.runner.ocr_read_text", return_value="  123456  "):
        runner = Runner(macro, macro_dir=tmp_path,
                        capturer=FakeCapturer(), input_normal=inp,
                        sleep=lambda s: None)
        res = runner.run()
    assert res.completed
    types = [e for e in inp.events if e[0] == "type"]
    assert types and types[0][1] == "OTP=123456"


def test_initial_variables_substituted(tmp_path):
    inp = FakeInput()
    macro = _macro_with(
        Step(
            id="t", name="x",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="hello ${name}"),
        ),
        variables={"name": "alice"},
    )
    runner = Runner(macro, macro_dir=tmp_path,
                    capturer=FakeCapturer(), input_normal=inp,
                    sleep=lambda s: None)
    runner.run()
    types = [e for e in inp.events if e[0] == "type"]
    assert types[0][1] == "hello alice"


def test_unknown_variable_left_intact(tmp_path):
    """Typo-tolerance: ``${typo}`` survives instead of crashing."""
    inp = FakeInput()
    macro = _macro_with(
        Step(
            id="t", name="x",
            trigger=TimeTrigger(delay_s=0),
            action=TypeAction(text="hi ${nope}"),
        )
    )
    runner = Runner(macro, macro_dir=tmp_path,
                    capturer=FakeCapturer(), input_normal=inp,
                    sleep=lambda s: None)
    runner.run()
    types = [e for e in inp.events if e[0] == "type"]
    assert types[0][1] == "hi ${nope}"


def test_macro_variables_round_trip(tmp_path):
    """The variables field round-trips through YAML serialisation."""
    from keymacro.storage.yaml_repo import load_macro, save_macro

    macro = _macro_with(
        Step(
            id="x", name="x",
            trigger=TimeTrigger(delay_s=0),
            action=WaitAction(duration_s=0),
        ),
        variables={"foo": "bar", "baz": "qux"},
    )
    p = tmp_path / "m.yaml"
    save_macro(macro, p)
    loaded = load_macro(p)
    assert loaded.variables == {"foo": "bar", "baz": "qux"}
