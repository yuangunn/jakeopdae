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


class CallMacroAction(BaseModel):
    """Run another macro file as if its steps were inlined here.

    Common use case: a "login.yaml" macro that opens the SSO page,
    types credentials, and waits for the dashboard. Other macros call
    it as their first step so the login dance is defined once.

    Path resolution:
        - Absolute path → used as-is.
        - Relative path → resolved against the *calling macro's*
          directory (so ``call_macro path: shared/login.yaml`` works
          regardless of where the user opens the macro from).

    Variable scope:
        Sub-macro starts with the parent's runtime variables (so the
        callee can read ``${otp}`` etc. set by the caller). After the
        call, the *callee's* writes are merged back into the parent
        scope, so a sub-macro that does ExtractTextAction(variable=
        'login_token') leaves that token visible to subsequent steps
        in the parent.

    Recursion guard: the runner tracks the active call chain and
    refuses to enter the same file twice in a single run, so a
    sub-macro accidentally calling itself doesn't blow the stack.
    """

    type: Literal["call_macro"] = "call_macro"
    path: str
    """Macro YAML to invoke. Relative paths resolve against the
    parent macro's directory."""

    @field_validator("path")
    @classmethod
    def _non_empty_path(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("path must not be empty")
        return v


_HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]


class HttpAction(BaseModel):
    """Send an HTTP request to a URL.

    Common use cases:
        - Webhook ping when a long-running macro finishes ("done" event)
        - Trigger an n8n / Zapier flow from inside a macro chain
        - Hit an internal API to log "user X completed training"

    Response handling: when ``store_in`` is set, the response body
    (decoded as text) is written into ``runner._vars[store_in]``, so
    later steps can ``${var}`` it. When unset, we discard the body.

    Status semantics: a response in the 2xx/3xx range counts as
    success. 4xx/5xx raise so on_failure routing kicks in. Network /
    DNS / TLS errors also raise — callers can pair this with
    ``on_failure='retry'`` for transient network glitches.

    Why a model field for headers (Mapping) rather than a flat list:
    YAML serialisation of a flat dict is more readable, and the few
    times we'd want duplicate header names (Set-Cookie etc.) are on
    the *response* side, not request.
    """

    type: Literal["http"] = "http"
    url: str
    method: _HttpMethod = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    """Request body. Plain text or JSON-encoded — content-type isn't
    auto-set, so include it in ``headers`` if you mean JSON."""
    timeout_s: float = 10.0
    store_in: str = ""
    """Variable name to receive the response body. Empty = discard.

    Type is str (not Optional) because pydantic discriminated unions
    serialise None back as a key in YAML, which is uglier than an
    empty string sentinel."""

    @field_validator("url")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url must not be empty")
        return v

    @field_validator("timeout_s")
    @classmethod
    def _positive_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("timeout_s must be > 0")
        return v


_ClipboardOp = Literal["copy", "paste", "set"]


class ClipboardAction(BaseModel):
    """Read/write the OS clipboard.

    Three operations:
        - ``copy``: send Ctrl+C (or Cmd+C on macOS) to capture whatever
          is currently selected in the foreground app, then store the
          clipboard text in the runtime variable named ``variable``.
          Useful with ExtractTextAction to grab the focus's content
          without going through OCR.
        - ``paste``: send Ctrl+V — pastes the OS clipboard's *current*
          contents into the focused field. Cheaper than re-typing for
          long strings, and IME-friendly (the OS handles Hangul).
        - ``set``: programmatically write ``text`` (with ``${var}``
          substitution) into the OS clipboard without touching the
          keyboard. Pair with a separate KeyAction(ctrl+v) to paste,
          or leave the data on the clipboard for the user.

    Why a single discriminated action with an ``op`` field rather than
    three separate types: the difference is only one parameter, the
    YAML stays compact, and the form picker can render a single tile.
    """

    type: Literal["clipboard"] = "clipboard"
    op: _ClipboardOp = "set"
    text: str = ""
    """Used only when ``op == 'set'``. Supports ``${var}`` substitution."""
    variable: str = "clipboard"
    """Used only when ``op == 'copy'``. The runtime variable that
    receives the captured text."""


Action = Annotated[
    Union[
        ClickAction,
        KeyAction,
        TypeAction,
        DragAction,
        WaitAction,
        ClipboardAction,
        HttpAction,
        CallMacroAction,
        WebClickAction,
        WebTypeAction,
        WebNavigateAction,
        ExtractTextAction,
    ],
    Field(discriminator="type"),
]
