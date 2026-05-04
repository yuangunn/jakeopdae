"""StepForm combobox regression — schema keys flow through the form
unchanged even though the displayed labels are Korean.

The previous bug: ``QComboBox.addItems(["left","right"])`` followed by
``setItemText(0, "왼쪽")`` made ``currentText()`` return the Korean
label, which was then fed to Pydantic as the schema value and crashed
with ``Input should be 'left', 'right' or 'middle'``. The fix is to
store the schema key as ``userData`` and read it via ``currentData()``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _form(qapp):
    from keymacro.ui.step_form import StepForm
    return StepForm()


# --- ClickAction (the one that originally crashed) ---------------------


def test_click_action_round_trip_preserves_button_and_input_mode(qapp):
    from keymacro.models import ClickAction, Step, TimeTrigger

    form = _form(qapp)
    original = Step(
        id="s1", name="x",
        trigger=TimeTrigger(delay_s=0),
        action=ClickAction(x=5, y=6, button="right", input_mode="raw"),
    )
    form.load_step(original)
    rebuilt = form.to_step()
    assert rebuilt.action.button == "right"
    assert rebuilt.action.input_mode == "raw"


def test_click_action_left_default(qapp):
    from keymacro.models import ClickAction, Step, TimeTrigger

    form = _form(qapp)
    original = Step(
        id="s2", name="x",
        trigger=TimeTrigger(delay_s=0),
        action=ClickAction(x=0, y=0),  # defaults: left + normal
    )
    form.load_step(original)
    rebuilt = form.to_step()
    assert rebuilt.action.button == "left"
    assert rebuilt.action.input_mode == "normal"


# --- WebClickAction (the one in the user's bug report) -----------------


def test_web_click_round_trip_preserves_button(qapp):
    from keymacro.models import Step, TimeTrigger, WebClickAction

    form = _form(qapp)
    original = Step(
        id="s3", name="x",
        trigger=TimeTrigger(delay_s=0),
        action=WebClickAction(
            selector="button:has-text('다음')",
            button="middle",
            double=True,
            force=True,
        ),
    )
    form.load_step(original)
    rebuilt = form.to_step()
    assert rebuilt.action.button == "middle"
    assert rebuilt.action.double is True
    assert rebuilt.action.force is True


# --- KeyAction.input_mode + DragAction.button --------------------------


def test_key_action_input_mode_preserved(qapp):
    from keymacro.models import KeyAction, Step, TimeTrigger

    form = _form(qapp)
    original = Step(
        id="s4", name="x",
        trigger=TimeTrigger(delay_s=0),
        action=KeyAction(keys="ctrl+c", input_mode="raw"),
    )
    form.load_step(original)
    rebuilt = form.to_step()
    assert rebuilt.action.input_mode == "raw"


def test_drag_action_button_preserved(qapp):
    from keymacro.models import DragAction, Step, TimeTrigger

    form = _form(qapp)
    original = Step(
        id="s5", name="x",
        trigger=TimeTrigger(delay_s=0),
        action=DragAction(x1=0, y1=0, x2=10, y2=10, button="right"),
    )
    form.load_step(original)
    rebuilt = form.to_step()
    assert rebuilt.action.button == "right"


# --- WebUrlTrigger.mode + WebElementVisibleTrigger.state ---------------


def test_web_url_trigger_mode_preserved(qapp):
    from keymacro.models import Step, WaitAction, WebUrlTrigger

    form = _form(qapp)
    original = Step(
        id="s6", name="x",
        trigger=WebUrlTrigger(pattern="/lec", mode="regex", timeout_s=1.0),
        action=WaitAction(duration_s=0),
    )
    form.load_step(original)
    rebuilt = form.to_step()
    assert rebuilt.trigger.mode == "regex"


def test_web_element_state_preserved(qapp):
    from keymacro.models import Step, WaitAction, WebElementVisibleTrigger

    form = _form(qapp)
    original = Step(
        id="s7", name="x",
        trigger=WebElementVisibleTrigger(
            selector="button", state="hidden", timeout_s=1.0,
        ),
        action=WaitAction(duration_s=0),
    )
    form.load_step(original)
    rebuilt = form.to_step()
    assert rebuilt.trigger.state == "hidden"


# --- WebNavigateAction.wait_until --------------------------------------


def test_web_navigate_wait_until_preserved(qapp):
    from keymacro.models import Step, TimeTrigger, WebNavigateAction

    form = _form(qapp)
    original = Step(
        id="s8", name="x",
        trigger=TimeTrigger(delay_s=0),
        action=WebNavigateAction(
            url="https://example.com", wait_until="networkidle",
        ),
    )
    form.load_step(original)
    rebuilt = form.to_step()
    assert rebuilt.action.wait_until == "networkidle"


# --- Step.on_failure ---------------------------------------------------


def test_on_failure_preserved(qapp):
    from keymacro.models import Step, TimeTrigger, WaitAction

    form = _form(qapp)
    for failure_mode in ("abort", "skip", "retry"):
        original = Step(
            id=f"s_{failure_mode}", name="x",
            trigger=TimeTrigger(delay_s=0),
            action=WaitAction(duration_s=0),
            on_failure=failure_mode,
            retry_count=2 if failure_mode == "retry" else 0,
        )
        form.load_step(original)
        rebuilt = form.to_step()
        assert rebuilt.on_failure == failure_mode, (
            f"on_failure {failure_mode!r} round-trip failed"
        )
