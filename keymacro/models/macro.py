"""A Macro is a named, ordered list of steps with a global runtime cap."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, field_validator

from .humanization import HumanizationConfig
from .step import Step
from .web import WebSessionConfig


_RunMode = Literal["sequential", "parallel"]


class Macro(BaseModel):
    """Top-level macro definition.

    ``max_total_runtime_s`` is a safety cutoff that aborts the macro if it
    has been running longer than the budget — protects against infinite
    polling loops or runaway branching.

    ``mode`` switches the runner between two execution models:

        - ``"sequential"`` (default) — steps run one after another; the
          next step starts only when the current step's trigger fires
          and its action completes. ``on_success_goto`` /
          ``on_failure_goto`` drive branching.

        - ``"parallel"`` — every step's trigger is watched concurrently
          in a short round-robin polling loop. As soon as *any* trigger
          matches, that step's action runs; then the loop resumes
          watching all triggers again. Useful for "the lecture's 다음
          버튼 보이면 클릭, 퀴즈 시작 보이면 정답 입력, 강의 끝 보이면
          다음 강의로" workflows where multiple unrelated events can
          happen in any order. ``Step.priority`` decides which one wins
          when more than one trigger matches in the same polling pass.
    """

    name: str
    description: str = ""
    steps: list[Step]
    max_total_runtime_s: float = 3600.0
    mode: _RunMode = "sequential"
    web_session: Optional[WebSessionConfig] = None
    """Browser session config; only constructed if a web step is present.
    ``None`` means use defaults (attach to localhost:9222) when needed."""
    variables: dict[str, str] = {}
    """Initial macro-level variables. Steps can reference them in any
    string field via ``${name}`` substitution; ``ExtractTextAction``
    populates new ones at runtime."""
    humanization: HumanizationConfig = HumanizationConfig()
    """Anti-bot-detection knobs (timing jitter, click position
    jitter, typing-interval jitter). All zero by default = original
    deterministic behaviour. See :class:`HumanizationConfig`."""

    @field_validator("name")
    @classmethod
    def _name_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("macro name must not be empty")
        return v

    @field_validator("steps")
    @classmethod
    def _unique_ids(cls, v: list[Step]) -> list[Step]:
        ids = [s.id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique within a macro")
        return v

    @field_validator("max_total_runtime_s")
    @classmethod
    def _runtime_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("max_total_runtime_s must be >= 0")
        return v

    def step_by_id(self, step_id: str) -> Step:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise KeyError(f"no step with id {step_id!r}")
