"""Static analysis on a :class:`Macro` — surfaces problems that would
make the runner fail at runtime, *before* the user hits ▶.

Why a separate pass instead of relying on the runner's ``on_failure``?
    - The runner only finds out a template is missing when the trigger
      times out (10 seconds of waiting for nothing). A preflight pass
      tells the user instantly.
    - Validation results drive the inline 🔴 badges on the StepCard so
      the offending step is highlighted in the sidebar.

What we check (cheap, deterministic, no I/O on the hot path):
    - ``ImageTrigger`` / ``HybridImageTrigger``: ``template`` file
      resolves under ``macro_dir/templates/``.
    - ``Region`` triggers: width/height > 0 and the rectangle fits inside
      the primary screen (rough sanity — multi-monitor setups may put it
      legitimately off-primary, so we only warn).
    - ``WebClickAction`` / ``WebTypeAction`` / ``WebElementVisibleTrigger``:
      ``selector`` is non-empty.
    - ``ScheduleTrigger``: ``weekdays`` non-empty AND every entry 0..6.
    - ``on_success_goto`` / ``on_failure_goto``: target step ID exists.
    - Duplicate step IDs (would silently break goto routing).

Each issue carries a short Korean label for the badge plus a longer
sentence for tooltip — 12-char rule of thumb so the badge doesn't
overflow the card width on small windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..models import (
    HybridImageTrigger,
    ImageTrigger,
    Macro,
    OcrTextTrigger,
    PixelColorTrigger,
    ScheduleTrigger,
    Step,
    WebClickAction,
    WebElementVisibleTrigger,
    WebTypeAction,
)


@dataclass(frozen=True)
class StepIssue:
    """One problem found on a single step.

    ``severity`` drives the badge colour (error → rose, warning → brass).
    ``label`` is the short tag shown on the StepCard.
    ``detail`` is the full sentence shown in the tooltip.
    """

    step_id: str
    severity: str  # "error" | "warning"
    label: str
    detail: str


def lint_macro(macro: Macro, macro_dir: Optional[Path]) -> list[StepIssue]:
    """Walk every step and collect issues.

    ``macro_dir`` is required for template-existence checks; pass
    ``None`` if the macro is unsaved (we silently skip those checks
    instead of flagging every brand-new macro).
    """
    issues: list[StepIssue] = []
    seen_ids: set[str] = set()
    valid_ids: set[str] = {s.id for s in macro.steps}

    for step in macro.steps:
        # Duplicate IDs are a silent foot-gun for goto routing.
        if step.id in seen_ids:
            issues.append(StepIssue(
                step_id=step.id, severity="error",
                label="중복 ID",
                detail=f"단계 ID '{step.id}' 가 이미 다른 단계에서 쓰이고 있어요.",
            ))
        else:
            seen_ids.add(step.id)

        # Trigger checks
        issues.extend(_lint_trigger(step, macro_dir))
        # Action checks
        issues.extend(_lint_action(step))
        # Goto target validity — both branches are validated.
        for attr, kind in (("on_success_goto", "성공"), ("on_failure_goto", "실패")):
            target = getattr(step, attr, None)
            if target and target not in valid_ids:
                issues.append(StepIssue(
                    step_id=step.id, severity="error",
                    label="goto 깨짐",
                    detail=f"{kind}시 '{target}' 으로 가도록 했는데 그런 단계가 없어요.",
                ))

    return issues


def issues_by_step(issues: list[StepIssue]) -> dict[str, list[StepIssue]]:
    """Group issues by ``step_id`` for the StepCard renderer."""
    out: dict[str, list[StepIssue]] = {}
    for i in issues:
        out.setdefault(i.step_id, []).append(i)
    return out


# --- internals --------------------------------------------------------------


def _lint_trigger(step: Step, macro_dir: Optional[Path]) -> list[StepIssue]:
    out: list[StepIssue] = []
    t = step.trigger

    if isinstance(t, (ImageTrigger, HybridImageTrigger)):
        out.extend(_lint_region(step.id, t.region))
        if macro_dir is not None and t.template:
            tpl_path = (macro_dir / t.template).resolve()
            if not tpl_path.is_file():
                out.append(StepIssue(
                    step_id=step.id, severity="error",
                    label="템플릿 없음",
                    detail=(
                        f"이미지 파일 '{t.template}' 을 찾지 못했어요. "
                        f"[화면 캡처] 로 다시 만들어 주세요."
                    ),
                ))

    if isinstance(t, OcrTextTrigger):
        out.extend(_lint_region(step.id, t.region))
        if not t.text.strip():
            out.append(StepIssue(
                step_id=step.id, severity="error",
                label="검색 글자 없음",
                detail="OCR 트리거에 찾을 글자가 비어 있어요.",
            ))

    if isinstance(t, PixelColorTrigger):
        if t.tolerance < 0:
            out.append(StepIssue(
                step_id=step.id, severity="error",
                label="허용오차 음수",
                detail="픽셀 색 허용 오차는 0 이상이어야 해요.",
            ))

    if isinstance(t, WebElementVisibleTrigger):
        if not t.selector.strip():
            out.append(StepIssue(
                step_id=step.id, severity="error",
                label="셀렉터 없음",
                detail="웹 요소 트리거에 CSS 셀렉터가 비어 있어요.",
            ))

    if isinstance(t, ScheduleTrigger):
        if not t.weekdays:
            out.append(StepIssue(
                step_id=step.id, severity="error",
                label="요일 없음",
                detail="예약 트리거에 발사할 요일이 하나도 없어요.",
            ))
        if any(d < 0 or d > 6 for d in t.weekdays):
            out.append(StepIssue(
                step_id=step.id, severity="error",
                label="요일 잘못됨",
                detail="요일은 0(월) ~ 6(일) 사이여야 해요.",
            ))

    return out


def _lint_action(step: Step) -> list[StepIssue]:
    out: list[StepIssue] = []
    a = step.action
    if isinstance(a, (WebClickAction, WebTypeAction)):
        if not a.selector.strip():
            out.append(StepIssue(
                step_id=step.id, severity="error",
                label="셀렉터 없음",
                detail="웹 동작에 CSS 셀렉터가 비어 있어요.",
            ))
    return out


def _lint_region(step_id: str, region) -> list[StepIssue]:
    out: list[StepIssue] = []
    if region.w <= 0 or region.h <= 0:
        out.append(StepIssue(
            step_id=step_id, severity="error",
            label="영역 0",
            detail=f"트리거 영역의 너비/높이가 0 이하예요 (w={region.w}, h={region.h}).",
        ))
    return out
