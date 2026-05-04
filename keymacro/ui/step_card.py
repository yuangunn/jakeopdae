"""StepCard — compact numbered card with prose summary.

Layout (single card, top to bottom, ~60–80px tall idle):
  [stripe 3px / 4px when active]
  [STEP 01 · badge · name ……………………… 복제 삭제]
  [trigger sentence as headline (1 line, elide if needed)]
  [→ action sentence (1 line, elide if needed) · meta tags inline]
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models import (
    Action,
    ClickAction,
    DragAction,
    ExtractTextAction,
    HybridImageTrigger,
    ImageTrigger,
    KeyAction,
    OcrTextTrigger,
    PixelColorTrigger,
    ScheduleTrigger,
    Step,
    TimeTrigger,
    TypeAction,
    WaitAction,
    WebClickAction,
    WebElementVisibleTrigger,
    WebNavigateAction,
    WebTypeAction,
    WebUrlTrigger,
)
from .theme import C, STRIPE


_TRIGGER_LABEL = {
    "image": "이미지",
    "time": "시간",
    "pixel": "픽셀",
    "web_element": "웹 요소",
    "web_url": "URL",
    "hybrid_image": "이미지+URL",
    "ocr_text": "텍스트",
    "schedule": "예약",
}


def _trigger_kind(step: Step) -> str:
    if isinstance(step.trigger, ImageTrigger):
        return "image"
    if isinstance(step.trigger, TimeTrigger):
        return "time"
    if isinstance(step.trigger, PixelColorTrigger):
        return "pixel"
    if isinstance(step.trigger, WebElementVisibleTrigger):
        return "web_element"
    if isinstance(step.trigger, WebUrlTrigger):
        return "web_url"
    if isinstance(step.trigger, HybridImageTrigger):
        return "hybrid_image"
    if isinstance(step.trigger, OcrTextTrigger):
        return "ocr_text"
    if isinstance(step.trigger, ScheduleTrigger):
        return "schedule"
    return "image"


def trigger_sentence(step: Step) -> str:
    t = step.trigger
    if isinstance(t, ImageTrigger):
        r = t.region
        return (
            f"이미지 {t.template} 이(가) "
            f"({r.x}, {r.y}) ~ ({r.x + r.w}, {r.y + r.h}) 안에 보이면"
        )
    if isinstance(t, TimeTrigger):
        return f"{t.delay_s:g}초 기다린 뒤"
    if isinstance(t, PixelColorTrigger):
        rr, gg, bb = t.rgb
        return (
            f"({t.x}, {t.y}) 위치의 픽셀 색이 "
            f"RGB({rr}, {gg}, {bb}) ±{t.tolerance} 가 되면"
        )
    if isinstance(t, WebElementVisibleTrigger):
        scope = f" ({t.url_contains} 페이지에서)" if t.url_contains else ""
        return f"웹 요소 {t.selector!r}{scope} 가 보이면"
    if isinstance(t, WebUrlTrigger):
        mode_kr = {"contains": "포함", "regex": "정규식 매칭", "exact": "정확히 일치"}[t.mode]
        return f"현재 URL이 '{t.pattern}' ({mode_kr}) 이면"
    if isinstance(t, HybridImageTrigger):
        r = t.region
        return (
            f"브라우저가 '{t.url_contains}' 페이지일 때 "
            f"이미지 {t.template} 이(가) "
            f"({r.x}, {r.y}) ~ ({r.x + r.w}, {r.y + r.h}) 에 보이면"
        )
    if isinstance(t, OcrTextTrigger):
        r = t.region
        return (
            f"({r.x}, {r.y}) ~ ({r.x + r.w}, {r.y + r.h}) 영역에서 "
            f"\"{t.text}\" 텍스트가 읽히면"
        )
    if isinstance(t, ScheduleTrigger):
        days_kr = ["월", "화", "수", "목", "금", "토", "일"]
        if len(t.weekdays) == 7:
            day_str = "매일"
        elif t.weekdays == [0, 1, 2, 3, 4]:
            day_str = "평일"
        elif t.weekdays == [5, 6]:
            day_str = "주말"
        else:
            day_str = ", ".join(days_kr[d] for d in t.weekdays)
        return f"{day_str} {t.at}이 되면"
    return "(알 수 없는 조건)"


def action_sentence(action: Action) -> str:
    if isinstance(action, ClickAction):
        btn = {"left": "왼쪽", "right": "오른쪽", "middle": "가운데"}.get(action.button, action.button)
        click_kind = "더블클릭한다" if action.double else "클릭한다"
        if action.relative_to_match:
            ox = f"+{action.x}" if action.x >= 0 else f"{action.x}"
            oy = f"+{action.y}" if action.y >= 0 else f"{action.y}"
            return f"→ 매칭 위치를 {btn} {click_kind} (오프셋 {ox}, {oy})"
        return f"→ ({action.x}, {action.y}) 를 {btn} {click_kind}"
    if isinstance(action, KeyAction):
        return f"→ 키 [{action.keys}] 를 누른다"
    if isinstance(action, TypeAction):
        text = action.text if len(action.text) <= 24 else action.text[:24] + "…"
        return f"→ \"{text}\" 입력한다"
    if isinstance(action, DragAction):
        return f"→ ({action.x1}, {action.y1}) → ({action.x2}, {action.y2}) 끈다"
    if isinstance(action, WaitAction):
        return f"→ {action.duration_s:g}초 멈춘다"
    if isinstance(action, WebClickAction):
        kind = "더블클릭한다" if action.double else "클릭한다"
        btn = {"left": "왼쪽", "right": "오른쪽", "middle": "가운데"}.get(action.button, action.button)
        forced = " (강제)" if action.force else ""
        return f"→ 웹 요소 {action.selector!r} 를 {btn} {kind}{forced}"
    if isinstance(action, WebTypeAction):
        text = action.text if len(action.text) <= 24 else action.text[:24] + "…"
        return f"→ 웹 요소 {action.selector!r} 에 \"{text}\" 입력한다"
    if isinstance(action, WebNavigateAction):
        return f"→ '{action.url}' 로 이동한다"
    if isinstance(action, ExtractTextAction):
        r = action.region
        return (
            f"→ ({r.x}, {r.y}) ~ ({r.x + r.w}, {r.y + r.h}) 영역의 텍스트를 "
            f"읽어 ${{{action.variable}}} 에 저장한다"
        )
    return "→ (알 수 없는 동작)"


def _meta_tags(step: Step) -> list[str]:
    out: list[str] = []
    if step.repeat > 1:
        out.append(f"×{step.repeat}")
    if step.on_failure == "skip":
        out.append("실패→건너뜀")
    elif step.on_failure == "retry":
        out.append(f"재시도 {step.retry_count}")
    if step.on_success_goto:
        out.append(f"→ {step.on_success_goto}")
    return out


# ---------------------------------------------------------------------------


class StepStripe(QFrame):
    """The 3px (4px when active) coloured bar on top of a step card."""

    def __init__(self, kind: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self._apply(kind)

    def _apply(self, kind: str, active: bool = False) -> None:
        self.setStyleSheet(
            f"background-color: {STRIPE.get(kind, C['outline'])};"
            f" border: none;"
            f" border-top-left-radius: 10px;"
            f" border-top-right-radius: 10px;"
        )
        self.setFixedHeight(4 if active else 3)

    def set_kind(self, kind: str) -> None:
        self._apply(kind, self.height() >= 4)

    def set_active(self, active: bool) -> None:
        # Re-derive kind from current colour by walking the stripe map; cheap.
        for k, v in STRIPE.items():
            if v in self.styleSheet():
                self._apply(k, active)
                return
        self._apply("image", active)


class StepCard(QFrame):
    selected = Signal(int)
    delete_requested = Signal(int)
    duplicate_requested = Signal(int)

    def __init__(self, step: Step, row: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "step-card")
        self.setProperty("state", "idle")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setMouseTracking(True)
        self._row = row
        self._step = step
        self._build_ui()
        self._refresh()

    def set_row(self, row: int) -> None:
        self._row = row
        self._number_lbl.setText(f"STEP {row + 1:02d}")

    def update_step(self, step: Step) -> None:
        self._step = step
        self._refresh()

    def set_active(self, active: bool) -> None:
        self.setProperty("state", "active" if active else "idle")
        self._stripe.set_active(active)
        self._reapply_style()

    def set_error(self, error: bool) -> None:
        self.setProperty("state", "error" if error else "idle")
        self._reapply_style()

    # --- assembly -------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stripe = StepStripe(_trigger_kind(self._step), self)
        layout.addWidget(self._stripe)

        body = QWidget(self)
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(12, 8, 10, 10)
        body_l.setSpacing(4)

        # --- top row: STEP nn · badge · name ……  복제 삭제 ----------------
        top = QHBoxLayout()
        top.setSpacing(8)

        self._number_lbl = QLabel(f"STEP {self._row + 1:02d}")
        self._number_lbl.setStyleSheet(
            f"color: {C['on-surface-variant']};"
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
            f"font-size: 11px; font-weight: 700; letter-spacing: 0.8px;"
        )
        top.addWidget(self._number_lbl)

        self._badge = QLabel()
        self._badge.setAlignment(Qt.AlignCenter)
        top.addWidget(self._badge)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color: {C['on-surface-variant']}; font-size: 11px;"
        )
        top.addWidget(self._title_lbl, 1)

        self._dup_btn = QPushButton("복제")
        self._dup_btn.setProperty("role", "icon-mini")
        self._dup_btn.setCursor(Qt.PointingHandCursor)
        self._dup_btn.clicked.connect(lambda: self.duplicate_requested.emit(self._row))
        top.addWidget(self._dup_btn)

        self._del_btn = QPushButton("삭제")
        self._del_btn.setProperty("role", "danger-ghost")
        self._del_btn.setCursor(Qt.PointingHandCursor)
        self._del_btn.clicked.connect(lambda: self.delete_requested.emit(self._row))
        top.addWidget(self._del_btn)

        body_l.addLayout(top)

        # --- trigger sentence (single line, elide) -----------------------
        self._trigger_lbl = QLabel()
        self._trigger_lbl.setStyleSheet(
            f"color: {C['on-surface']}; font-size: 13px; font-weight: 600;"
        )
        self._trigger_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body_l.addWidget(self._trigger_lbl)

        # --- action sentence + inline meta ------------------------------
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)
        self._action_lbl = QLabel()
        self._action_lbl.setStyleSheet(
            f"color: {C['on-surface-variant']}; font-size: 12px;"
        )
        bottom_row.addWidget(self._action_lbl, 1)
        self._meta_row = bottom_row
        body_l.addLayout(bottom_row)

        layout.addWidget(body)

    def _refresh(self) -> None:
        kind = _trigger_kind(self._step)
        self._stripe.set_kind(kind)

        self._badge.setProperty("badge", kind)
        self._badge.setText(_TRIGGER_LABEL[kind])
        self._reapply_style()

        self._title_lbl.setText(self._step.name or "(이름 없음)")

        # Trigger / action sentences with elision
        fm_t = QFontMetrics(self._trigger_lbl.font())
        fm_a = QFontMetrics(self._action_lbl.font())
        max_w = max(self.width() - 36, 200)
        self._trigger_lbl.setText(
            fm_t.elidedText(trigger_sentence(self._step), Qt.ElideMiddle, max_w)
        )
        self._action_lbl.setText(
            fm_a.elidedText(action_sentence(self._step.action), Qt.ElideRight, max_w)
        )

        # Replace any existing meta-tag chips (after the action label)
        # We track children we added by tag.
        for i in reversed(range(self._meta_row.count())):
            item = self._meta_row.itemAt(i)
            w = item.widget()
            if w is not None and w is not self._action_lbl:
                w.deleteLater()
                self._meta_row.takeAt(i)
        for tag in _meta_tags(self._step):
            lbl = QLabel(tag)
            lbl.setProperty("role", "meta-tag")
            self._meta_row.addWidget(lbl)

    def _reapply_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)

    # --- mouse selection ------------------------------------------------

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton:
            self.selected.emit(self._row)
        super().mousePressEvent(e)

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        # Re-elide sentences when card width changes
        self._refresh_sentences_only()

    def _refresh_sentences_only(self) -> None:
        fm_t = QFontMetrics(self._trigger_lbl.font())
        fm_a = QFontMetrics(self._action_lbl.font())
        max_w = max(self.width() - 36, 200)
        self._trigger_lbl.setText(
            fm_t.elidedText(trigger_sentence(self._step), Qt.ElideMiddle, max_w)
        )
        self._action_lbl.setText(
            fm_a.elidedText(action_sentence(self._step.action), Qt.ElideRight, max_w)
        )

    def sizeHint(self) -> QSize:  # noqa: N802
        s = super().sizeHint()
        return QSize(s.width(), max(s.height(), 76))
