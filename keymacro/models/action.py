"""Action models. An action is what runs after a trigger fires."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator

from .ocr import ExtractTextAction
from .web import WebClickAction, WebNavigateAction, WebTypeAction


_InputMode = Literal["normal", "raw"]
_Button = Literal["left", "right", "middle"]


class ClickAction(BaseModel):
    """Click at absolute (x, y) or as an offset from the last image-match center."""

    type: Literal["click"] = "click"
    x: int = 0
    y: int = 0
    button: _Button = "left"
    relative_to_match: bool = False
    double: bool = False
    input_mode: _InputMode = "normal"


class KeyAction(BaseModel):
    """Press a key combination, e.g. ``ctrl+c`` or ``enter``."""

    type: Literal["key"] = "key"
    keys: str
    input_mode: _InputMode = "normal"

    @field_validator("keys")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("keys must not be empty")
        return v


class TypeAction(BaseModel):
    """Type a string of text via the keyboard backend."""

    type: Literal["type"] = "type"
    text: str
    interval_s: float = 0.0

    @field_validator("interval_s")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("interval_s must be >= 0")
        return v


class DragAction(BaseModel):
    """Drag from (x1, y1) to (x2, y2) with the chosen mouse button."""

    type: Literal["drag"] = "drag"
    x1: int
    y1: int
    x2: int
    y2: int
    duration_s: float = 0.3
    button: _Button = "left"
    input_mode: _InputMode = "normal"

    @field_validator("duration_s")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("duration_s must be >= 0")
        return v


class WaitAction(BaseModel):
    """Sleep for ``duration_s``."""

    type: Literal["wait"] = "wait"
    duration_s: float

    @field_validator("duration_s")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("duration_s must be >= 0")
        return v


Action = Annotated[
    Union[
        ClickAction,
        KeyAction,
        TypeAction,
        DragAction,
        WaitAction,
        WebClickAction,
        WebTypeAction,
        WebNavigateAction,
        ExtractTextAction,
    ],
    Field(discriminator="type"),
]
