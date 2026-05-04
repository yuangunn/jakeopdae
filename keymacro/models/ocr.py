"""OCR (text-reading) triggers and actions."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class OcrTextTrigger(BaseModel):
    """Wait until text matching ``text`` is read from ``region``.

    Tesseract is slower than pixel matching (≈100–300 ms per call), so
    ``poll_interval_s`` defaults higher than other triggers — set it to
    ``2.0`` or more for long-running watches to avoid hammering CPU.
    """

    type: Literal["ocr_text"] = "ocr_text"
    region: "Region"
    text: str
    mode: Literal["contains", "regex", "exact"] = "contains"
    case_sensitive: bool = False
    language: Literal["kor", "eng", "kor+eng", "jpn", "chi_sim", "chi_tra"] = "kor+eng"
    timeout_s: float = 30.0
    poll_interval_s: float = 1.0

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty")
        return v

    @field_validator("timeout_s", "poll_interval_s")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("must be >= 0")
        return v


class ExtractTextAction(BaseModel):
    """OCR a screen region and store the result into a macro variable.

    Used in combination with :class:`~keymacro.models.macro.Macro`'s
    variables system: a later step can reference ``${var_name}`` in any
    string field (TypeAction.text, web URLs, etc.).
    """

    type: Literal["extract_text"] = "extract_text"
    region: "Region"
    variable: str
    language: Literal["kor", "eng", "kor+eng", "jpn", "chi_sim", "chi_tra"] = "kor+eng"
    strip: bool = True
    """Trim leading/trailing whitespace + collapse internal whitespace."""

    @field_validator("variable")
    @classmethod
    def _variable_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("variable name must not be empty")
        if not v.replace("_", "").isalnum():
            raise ValueError(
                "variable name must be alphanumeric/underscore (no spaces or special chars)"
            )
        return v


# Forward reference resolved at import time when models package finishes loading.
from .trigger import Region  # noqa: E402

OcrTextTrigger.model_rebuild()
ExtractTextAction.model_rebuild()
