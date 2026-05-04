"""Template-matching behaviour."""

from __future__ import annotations

import cv2
import numpy as np

from keymacro.core.matcher import MatchResult, match_template

from .conftest import solid_bgr, textured_bgr


def test_finds_template_at_known_location():
    """Embed a textured needle inside a solid haystack and find it back."""
    needle = textured_bgr(20, 20, seed=1)
    haystack = solid_bgr(200, 200, (50, 50, 50))
    haystack[80:100, 60:80] = needle

    res = match_template(
        haystack, needle,
        region_origin=(0, 0),
        confidence=0.9,
        multi_scale=False,
    )

    assert res.found
    # Patch occupies cols 60..80 and rows 80..100 -> center (70, 90).
    assert abs(res.center_x - 70) <= 1
    assert abs(res.center_y - 90) <= 1
    assert res.confidence > 0.95


def test_returns_not_found_below_confidence_threshold():
    """A unique textured needle that does not appear in the haystack must not
    be reported as found."""
    needle = textured_bgr(20, 20, seed=2)
    haystack = textured_bgr(100, 100, seed=99)  # different texture, no overlap

    res = match_template(
        haystack, needle,
        region_origin=(0, 0),
        confidence=0.95,
        multi_scale=False,
    )

    assert not res.found


def test_region_origin_is_added_to_result_coordinates():
    needle = textured_bgr(10, 10, seed=3)
    haystack = solid_bgr(100, 100, (50, 50, 50))
    haystack[40:50, 30:40] = needle

    res = match_template(
        haystack, needle,
        region_origin=(500, 600),
        confidence=0.9,
        multi_scale=False,
    )

    assert res.found
    # Local center (35, 45) + origin (500, 600).
    assert abs(res.center_x - 535) <= 1
    assert abs(res.center_y - 645) <= 1


def test_needle_larger_than_haystack_returns_not_found():
    haystack = textured_bgr(10, 10, seed=10)
    needle = textured_bgr(20, 20, seed=11)

    res = match_template(
        haystack, needle,
        region_origin=(0, 0),
        confidence=0.5,
        multi_scale=False,
    )

    assert not res.found


def test_multi_scale_finds_resized_template():
    """A textured template scaled to a different size should be found by the
    multi-scale path but missed by the single-scale path."""
    needle = textured_bgr(20, 20, seed=42)
    needle_24 = cv2.resize(needle, (24, 24), interpolation=cv2.INTER_AREA)

    haystack = solid_bgr(200, 200, (10, 10, 10))
    haystack[80:104, 60:84] = needle_24

    res_no_scale = match_template(
        haystack, needle,
        region_origin=(0, 0),
        confidence=0.95,
        multi_scale=False,
    )
    res_with_scale = match_template(
        haystack, needle,
        region_origin=(0, 0),
        confidence=0.85,
        multi_scale=True,
        scale_min=1.0,
        scale_max=1.4,
        scale_steps=5,
    )

    # Without rescaling, the 20x20 needle has poor correlation with the 24x24
    # patch (different texture frequencies). Multi-scale finds it.
    assert not res_no_scale.found or res_no_scale.confidence < 0.95
    assert res_with_scale.found


def test_match_result_not_found_factory():
    res = MatchResult.not_found(0.42)
    assert not res.found
    assert res.confidence == 0.42
