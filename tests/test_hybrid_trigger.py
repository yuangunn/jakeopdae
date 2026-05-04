"""HybridImageTrigger — model + runner integration via fake URL reader."""

from __future__ import annotations

import cv2
import pytest
from pydantic import ValidationError
from unittest.mock import patch

from keymacro.core.runner import Runner
from keymacro.models import (
    ClickAction,
    HybridImageTrigger,
    Macro,
    Region,
    Step,
)

from .conftest import FakeCapturer, FakeInput, solid_bgr, textured_bgr


# --- model validation ----------------------------------------------------


def test_hybrid_rejects_empty_url():
    with pytest.raises(ValidationError):
        HybridImageTrigger(
            template="t.png",
            region=Region(x=0, y=0, w=10, h=10),
            url_contains="",
        )


def test_hybrid_rejects_empty_template():
    with pytest.raises(ValidationError):
        HybridImageTrigger(
            template="",
            region=Region(x=0, y=0, w=10, h=10),
            url_contains="example.com",
        )


def test_hybrid_round_trip():
    t = HybridImageTrigger(
        template="t.png",
        region=Region(x=10, y=20, w=100, h=200),
        url_contains="sela.yuhs.ac",
        url_mode="regex",
        browser="chrome",
        confidence=0.85,
    )
    data = t.model_dump(mode="json")
    t2 = HybridImageTrigger.model_validate(data)
    assert t2 == t


# --- runner integration --------------------------------------------------


def _make_macro(template_name: str, *, url: str = "example.com") -> Macro:
    return Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="hybrid",
                trigger=HybridImageTrigger(
                    template=template_name,
                    region=Region(x=0, y=0, w=50, h=50),
                    url_contains=url,
                    timeout_s=0.2,
                    poll_interval_s=0.01,
                    multi_scale=False,
                ),
                action=ClickAction(x=42, y=42),
            )
        ],
    )


def test_hybrid_fires_when_url_matches_and_image_visible(tmp_path):
    template = textured_bgr(10, 10, seed=21)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    template_disk = cv2.imread(str(tmp_path / "t.png"), cv2.IMREAD_COLOR)

    haystack = solid_bgr(50, 50, (0, 0, 0))
    haystack[10:20, 10:20] = template_disk
    cap = FakeCapturer(default=haystack)
    inp = FakeInput()
    macro = _make_macro("t.png", url="example.com")

    with patch(
        "keymacro.core.runner.read_browser_url",
        return_value="https://example.com/page",
    ):
        runner = Runner(
            macro, macro_dir=tmp_path,
            capturer=cap, input_normal=inp,
            sleep=lambda s: None,
        )
        res = runner.run()

    assert res.completed
    assert ("click", 42, 42, "left", False) in inp.events


def test_hybrid_skips_image_match_when_url_mismatches(tmp_path):
    """Even if the image is on screen, the wrong URL prevents firing."""
    template = textured_bgr(10, 10, seed=22)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    template_disk = cv2.imread(str(tmp_path / "t.png"), cv2.IMREAD_COLOR)
    haystack = solid_bgr(50, 50, (0, 0, 0))
    haystack[10:20, 10:20] = template_disk
    cap = FakeCapturer(default=haystack)
    inp = FakeInput()
    macro = _make_macro("t.png", url="example.com")

    with patch(
        "keymacro.core.runner.read_browser_url",
        return_value="https://other-site.com/page",
    ):
        runner = Runner(
            macro, macro_dir=tmp_path,
            capturer=cap, input_normal=inp,
            sleep=lambda s: None,
        )
        res = runner.run()

    assert not res.completed
    # Action must not have fired despite the image being visible.
    assert not any(e[0] == "click" for e in inp.events)


def test_hybrid_handles_unreadable_url(tmp_path):
    """When the URL reader returns None (UIA failed / no browser open),
    the URL guard fails closed so the trigger times out."""
    template = textured_bgr(10, 10, seed=23)
    cv2.imwrite(str(tmp_path / "t.png"), template)

    haystack = solid_bgr(50, 50, (0, 0, 0))
    cap = FakeCapturer(default=haystack)
    inp = FakeInput()
    macro = _make_macro("t.png", url="example.com")

    with patch("keymacro.core.runner.read_browser_url", return_value=None):
        runner = Runner(
            macro, macro_dir=tmp_path,
            capturer=cap, input_normal=inp,
            sleep=lambda s: None,
        )
        res = runner.run()

    assert not res.completed
    assert not any(e[0] == "click" for e in inp.events)


def test_hybrid_does_not_capture_screen_when_url_mismatches(tmp_path):
    """Performance: the URL-mismatch path should poll URL only, not the
    screen, to avoid burning CPU on the wrong page."""
    template = textured_bgr(10, 10, seed=24)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    cap = FakeCapturer(default=solid_bgr(50, 50, (0, 0, 0)))
    inp = FakeInput()
    macro = _make_macro("t.png", url="example.com")

    with patch(
        "keymacro.core.runner.read_browser_url",
        return_value="https://other.com/",
    ):
        runner = Runner(
            macro, macro_dir=tmp_path,
            capturer=cap, input_normal=inp,
            sleep=lambda s: None,
        )
        runner.run()

    assert not cap.calls, "screen capture should be skipped while URL mismatches"


def test_hybrid_url_modes_regex(tmp_path):
    template = textured_bgr(10, 10, seed=25)
    cv2.imwrite(str(tmp_path / "t.png"), template)
    template_disk = cv2.imread(str(tmp_path / "t.png"), cv2.IMREAD_COLOR)
    haystack = solid_bgr(50, 50, (0, 0, 0))
    haystack[10:20, 10:20] = template_disk
    cap = FakeCapturer(default=haystack)
    inp = FakeInput()

    macro = Macro(
        name="m",
        steps=[
            Step(
                id="s1", name="x",
                trigger=HybridImageTrigger(
                    template="t.png",
                    region=Region(x=0, y=0, w=50, h=50),
                    url_contains=r"/lec/\d+/complete",
                    url_mode="regex",
                    timeout_s=0.2,
                    poll_interval_s=0.01,
                    multi_scale=False,
                ),
                action=ClickAction(x=99, y=99),
            )
        ],
    )

    with patch(
        "keymacro.core.runner.read_browser_url",
        return_value="https://x.com/lec/123/complete",
    ):
        runner = Runner(
            macro, macro_dir=tmp_path,
            capturer=cap, input_normal=inp,
            sleep=lambda s: None,
        )
        res = runner.run()

    assert res.completed
    assert ("click", 99, 99, "left", False) in inp.events
