"""Trigger models. A trigger is the condition under which a step's action fires."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator

# NOTE: ``hybrid`` and ``web`` are imported AFTER ``Region`` is defined below
# to avoid a circular import (``hybrid.HybridImageTrigger`` references
# ``Region``).


class Region(BaseModel):
    """Screen region in absolute pixel coordinates (top-left origin)."""

    x: int
    y: int
    w: int
    h: int

    @field_validator("w", "h")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("region width/height must be positive")
        return v


class ImageTrigger(BaseModel):
    """Wait for a template image to appear inside ``region``.

    The match is computed with normalized cross-correlation. With
    ``multi_scale`` enabled the template is matched at several scales,
    which makes the trigger tolerant to DPI / window-size differences.
    """

    type: Literal["image"] = "image"
    template: str  # path relative to the macro YAML's directory
    region: Region
    confidence: float = 0.9
    timeout_s: float = 5.0
    poll_interval_s: float = 0.2
    multi_scale: bool = True
    scale_min: float = 0.9
    scale_max: float = 1.1
    scale_steps: int = 5

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            raise ValueError("confidence must be in (0, 1]")
        return v

    @field_validator("timeout_s", "poll_interval_s")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("must be >= 0")
        return v

    @field_validator("scale_steps")
    @classmethod
    def _steps_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("scale_steps must be >= 1")
        return v


class TimeTrigger(BaseModel):
    """Sleep for a fixed duration before firing the action."""

    type: Literal["time"] = "time"
    delay_s: float = 0.0

    @field_validator("delay_s")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("delay_s must be >= 0")
        return v


class PixelColorTrigger(BaseModel):
    """Wait until the pixel at (x, y) matches ``rgb`` within ``tolerance``."""

    type: Literal["pixel"] = "pixel"
    x: int
    y: int
    rgb: tuple[int, int, int]
    tolerance: int = 10
    timeout_s: float = 5.0
    poll_interval_s: float = 0.2

    @field_validator("rgb")
    @classmethod
    def _rgb_range(cls, v: tuple[int, int, int]) -> tuple[int, int, int]:
        for c in v:
            if not 0 <= c <= 255:
                raise ValueError("rgb components must be in 0..255")
        return v

    @field_validator("tolerance")
    @classmethod
    def _tolerance_range(cls, v: int) -> int:
        if not 0 <= v <= 255:
            raise ValueError("tolerance must be in 0..255")
        return v


# Now safe to import the modules that reference ``Region`` above.
from .hybrid import HybridImageTrigger  # noqa: E402  (deferred to break cycle)
from .ocr import OcrTextTrigger  # noqa: E402  (also deferred)
from .schedule import ScheduleTrigger  # noqa: E402
from .web import WebElementVisibleTrigger, WebUrlTrigger  # noqa: E402


Trigger = Annotated[
    Union[
        ImageTrigger,
        TimeTrigger,
        PixelColorTrigger,
        WebElementVisibleTrigger,
        WebUrlTrigger,
        HybridImageTrigger,
        OcrTextTrigger,
        ScheduleTrigger,
    ],
    Field(discriminator="type"),
]
