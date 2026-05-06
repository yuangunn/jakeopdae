"""A Step pairs a trigger with an action plus failure / branching policy."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .action import Action
from .trigger import Trigger


class Step(BaseModel):
    """One unit of work in a macro.

    The ``trigger`` is awaited (image polling, sleep, pixel polling); when it
    fires the ``action`` is executed. ``on_failure`` controls what happens
    when the trigger times out or the action raises.

    ``on_success_goto`` lets you jump to an arbitrary step id rather than the
    next one in the list, enabling simple branching.
    """

    id: str
    name: str = ""
    trigger: Trigger
    action: Action
    on_failure: Literal["abort", "skip", "retry"] = "abort"
    retry_count: int = 0
    on_success_goto: Optional[str] = None
    on_failure_goto: Optional[str] = None
    """Together with ``on_failure='skip'``, lets the macro branch on
    trigger timeouts or action errors. Example: a step that watches for
    "이미 로그인됨" — if it succeeds, ``on_success_goto: dashboard``;
    if it times out (i.e. user is logged out), the runner advances to
    the next step which begins the login flow."""
    repeat: int = 1
    priority: int = 0
    """Tie-breaker for parallel mode. When ``Macro.mode == 'parallel'``
    every step is polled each cycle; if more than one trigger matches
    in the same pass, the highest-priority step fires. Steps with the
    same priority break ties by list order. Ignored in sequential mode.
    """

    @field_validator("id")
    @classmethod
    def _id_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("step id must not be empty")
        return v

    @field_validator("retry_count")
    @classmethod
    def _retry_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("retry_count must be >= 0")
        return v

    @field_validator("repeat")
    @classmethod
    def _repeat_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("repeat must be >= 1")
        return v
