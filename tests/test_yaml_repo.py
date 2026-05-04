"""Round-trip serialisation of macros via YAML."""

from __future__ import annotations

import pytest

from keymacro.models import (
    ClickAction,
    ImageTrigger,
    Macro,
    PixelColorTrigger,
    Region,
    Step,
    TimeTrigger,
    WaitAction,
)
from keymacro.storage.yaml_repo import load_macro, save_macro


def test_round_trip_preserves_all_fields(tmp_path):
    m = Macro(
        name="test",
        description="round-trip me",
        steps=[
            Step(
                id="a",
                name="image step",
                trigger=ImageTrigger(
                    template="t.png",
                    region=Region(x=10, y=20, w=100, h=200),
                    confidence=0.85,
                    timeout_s=2.0,
                ),
                action=ClickAction(x=50, y=60, double=True, button="right"),
            ),
            Step(
                id="b",
                name="time step",
                trigger=TimeTrigger(delay_s=1.5),
                action=WaitAction(duration_s=0.5),
                on_failure="skip",
            ),
            Step(
                id="c",
                name="pixel step",
                trigger=PixelColorTrigger(x=10, y=20, rgb=(255, 0, 128)),
                action=ClickAction(x=0, y=0, relative_to_match=False),
                on_success_goto="a",
            ),
        ],
    )
    path = tmp_path / "macro.yaml"
    save_macro(m, path)

    loaded = load_macro(path)
    assert loaded == m


def test_save_is_atomic(tmp_path):
    """A successful save must replace the target in one ``rename`` op so
    a reader never sees a half-written file."""
    m = Macro(
        name="atomic",
        steps=[
            Step(
                id="a", name="a",
                trigger=TimeTrigger(delay_s=0),
                action=WaitAction(duration_s=0),
            )
        ],
    )
    path = tmp_path / "macro.yaml"
    save_macro(m, path)
    assert path.exists()
    # The temp sibling must not linger after a successful save.
    assert not (tmp_path / "macro.yaml.tmp").exists()


def test_load_empty_file_raises(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_macro(p)


def test_load_invalid_payload_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("name: bad\nsteps: not_a_list\n", encoding="utf-8")
    with pytest.raises(Exception):
        load_macro(p)
