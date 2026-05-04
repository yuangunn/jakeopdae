"""Multi-scale template matching using OpenCV.

The matcher returns a :class:`MatchResult` carrying the best confidence
score and — when the score clears the caller's threshold — the absolute
screen coordinates of the match center. Coordinates are in *screen* space
because the caller passes ``region_origin`` (the top-left of the captured
region in screen space) and we translate back.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2  # type: ignore[import-not-found]
import numpy as np


@dataclass(frozen=True)
class MatchResult:
    """Outcome of a template-match attempt."""

    found: bool
    confidence: float
    center_x: int
    center_y: int

    @classmethod
    def not_found(cls, best_score: float = 0.0) -> "MatchResult":
        return cls(found=False, confidence=float(best_score), center_x=0, center_y=0)


def match_template(
    haystack: np.ndarray,
    needle: np.ndarray,
    *,
    region_origin: tuple[int, int],
    confidence: float,
    multi_scale: bool = True,
    scale_min: float = 0.9,
    scale_max: float = 1.1,
    scale_steps: int = 5,
) -> MatchResult:
    """Find ``needle`` (BGR) inside ``haystack`` (BGR).

    Parameters
    ----------
    region_origin
        ``(left, top)`` of the haystack in absolute screen coordinates. The
        returned center is translated by this origin so the caller can click
        the result without further bookkeeping.
    confidence
        Minimum normalized correlation score (0..1) required for a match.
    multi_scale
        When ``True``, the needle is rescaled across ``scale_steps`` evenly
        spaced factors in ``[scale_min, scale_max]`` and the best score
        across all scales is kept.
    """
    if needle is None or haystack is None or needle.size == 0 or haystack.size == 0:
        return MatchResult.not_found()

    if not multi_scale or scale_steps <= 1:
        scales: list[float] = [1.0]
    else:
        scales = [float(s) for s in np.linspace(scale_min, scale_max, scale_steps)]

    best_score = -1.0
    best_loc = (0, 0)
    best_size = (needle.shape[1], needle.shape[0])

    for scale in scales:
        if abs(scale - 1.0) < 1e-6:
            scaled = needle
        else:
            new_w = max(1, int(round(needle.shape[1] * scale)))
            new_h = max(1, int(round(needle.shape[0] * scale)))
            scaled = cv2.resize(needle, (new_w, new_h), interpolation=cv2.INTER_AREA)

        if scaled.shape[0] > haystack.shape[0] or scaled.shape[1] > haystack.shape[1]:
            # Template would exceed the haystack at this scale; skip.
            continue

        result = cv2.matchTemplate(haystack, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > best_score:
            best_score = float(max_val)
            best_loc = max_loc
            best_size = (scaled.shape[1], scaled.shape[0])

    if best_score < 0:
        # Could not run match at any scale (e.g., needle larger than haystack).
        return MatchResult.not_found()

    if best_score < confidence:
        return MatchResult.not_found(best_score)

    cx = int(region_origin[0] + best_loc[0] + best_size[0] // 2)
    cy = int(region_origin[1] + best_loc[1] + best_size[1] // 2)
    return MatchResult(found=True, confidence=best_score, center_x=cx, center_y=cy)
