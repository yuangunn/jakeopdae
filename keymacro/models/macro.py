"""A Macro is a named, ordered list of steps with a global runtime cap."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator

from .step import Step
from .web import WebSessionConfig


class Macro(BaseModel):
    """Top-level macro definition.

    ``max_total_runtime_s`` is a safety cutoff that aborts the macro if it
    has been running longer than the budget — protects against infinite
    polling loops or runaway branching.
    """

    name: str
    description: str = ""
    steps: list[Step]
    max_total_runtime_s: float = 3600.0
    web_session: Optional[WebSessionConfig] = None
    """Browser session config; only constructed if a web step is present.
    ``None`` means use defaults (attach to localhost:9222) when needed."""
    variables: dict[str, str] = {}
    """Initial macro-level variables. Steps can reference them in any
    string field via ``${name}`` substitution; ``ExtractTextAction``
    populates new ones at runtime."""

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
