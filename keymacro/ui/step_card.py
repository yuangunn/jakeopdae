"""StepCard — compact numbered card with prose summary.

Layout (single card, top to bottom, ~60–80px tall idle):
  [stripe 3px / 4px when active]
  [STEP 01 · badge · name ……………………… 복제 삭제]
  [trigger sentence as headline (1 line, elide if needed)]
  [→ action sentence (1 line, elide if needed) · meta tags inline]
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QMimeData, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction, QColor, QDrag, QFontMetrics, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# Internal mime type for in-process step drag-drop reordering.
STEP_DRAG_MIME = "application/x-keymacro-step-row"

from ..core.preflight import StepIssue
from ..models import (
    Action,
    CallMacroAction,
    ClickAction,
    ClipboardAction,
    ClipboardChangeTrigger,
    DragAction,
    ExtractTextAction,
    HttpAction,
    HybridImageTrigger,
    ImageTrigger,
    KeyAction,
    NotifyAction,
    WindowResizeAction,
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
    "clipboard": "클립보드",
}


def _trigger_kind(step: Step) -> str:
    if isinstance(step.trigger, ImageTrigger):
        return "image"
    if isinstance(step.trigger, TimeTrigger):
        return "time"
    if isinstance(step.trigger, PixelColorTrigger):
        return "pixel"
    if isinstance(step.trigger, ClipboardChangeTrigger):
        return "clipboard"
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
    if isinstance(t, ClipboardChangeTrigger):
        return (
            f"클립보드에 패턴 \"{t.pattern}\" 의 텍스트가 들어오면 "
            f"(${{{t.capture_var}}} 에 저장)"
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
    if isinstance(action, ClipboardAction):
        if action.op == "copy":
            return f"→ 선택 영역을 복사 (Ctrl+C) 해서 ${{{action.variable}}} 에 저장"
        if action.op == "paste":
            return "→ 클립보드 내용 붙여넣기 (Ctrl+V)"
        # set
        text = action.text if len(action.text) <= 22 else action.text[:22] + "…"
        return f"→ 클립보드에 \"{text}\" 쓰기"
    if isinstance(action, HttpAction):
        url = action.url if len(action.url) <= 32 else action.url[:32] + "…"
        store = f" → ${{{action.store_in}}}" if action.store_in else ""
        return f"→ {action.method} {url}{store}"
    if isinstance(action, CallMacroAction):
        path = action.path if len(action.path) <= 36 else "…" + action.path[-32:]
        return f"→ 다른 매크로 실행: {path}"
    if isinstance(action, NotifyAction):
        text = action.text if len(action.text) <= 24 else action.text[:24] + "…"
        provider_kr = {
            "telegram": "텔레그램", "slack": "Slack",
            "discord": "Discord", "kakao_work": "카카오워크",
        }.get(action.provider, action.provider)
        return f"→ {provider_kr} 알림: \"{text}\""
    if isinstance(action, WindowResizeAction):
        target = "활성 창" if action.title_match.strip() == "<active>" else f"창 '{action.title_match}'"
        if action.mode == "bounds":
            return f"→ {target} 을 ({action.x},{action.y}) {action.w}×{action.h}로 옮기기"
        if action.mode == "maximize":
            return f"→ {target} 최대화"
        if action.mode == "minimize":
            return f"→ {target} 최소화"
        if action.mode == "restore":
            return f"→ {target} 복원"
        if action.mode == "fullscreen_monitor":
            return f"→ {target} 을 모니터 {action.monitor_index}번에 풀스크린"
        return f"→ {target} 조정"
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
        out.append(f"성공→{step.on_success_goto}")
    if step.on_failure_goto:
        out.append(f"실패→{step.on_failure_goto}")
    if step.priority != 0:
        out.append(f"우선순위 {step.priority:+d}")
    return out


# ---------------------------------------------------------------------------


# Card visuals (stripe + outline + background) are drawn in a single
# overridden ``paintEvent`` rather than via QSS. Why:
#
#   - QSS rounded-rect outlines and inset child widgets paint in
#     separate passes, so the stripe's top corners and the card's
#     rounded outline never landed on exactly the same pixels — the
#     1 px gap was visible on every corner.
#   - QSS border-radius rendering on QFrame can also miss the corner
#     antialiasing pixels under certain DPI settings, leaving the
#     four corners looking "잘린 듯" even without a stripe.
#
# Drawing everything inside one ``QPainter`` call with
# ``Antialiasing`` on, sharing the same ``QPainterPath`` for the
# rounded card outline AND for clipping the stripe, makes corner
# alignment automatic — they're literally the same geometry.


class StepCard(QFrame):
    selected = Signal(int)
    edit_requested = Signal(int)
    """Fired by the "✏ 편집" button or by a double-click on the card.
    The host opens a :class:`StepEditDialog` for this row."""
    delete_requested = Signal(int)
    duplicate_requested = Signal(int)
    test_requested = Signal(int)
    """Fired when the user picks "이 단계만 테스트" from the right-click
    menu. Host runs an ad-hoc one-step Macro using the same Runner."""
    preview_failure_requested = Signal(int)
    """Fired when the user clicks the "📷 실패 화면" mini-button on an
    errored card. Host opens FailurePreviewDialog with the cached image."""
    reorder_requested = Signal(int, int)
    """``(src_row, target_row)`` — fired when the user drops a card here.
    ``target_row`` is the *insertion* index in the *original* list
    (before removal of the source); the receiver is expected to do the
    correct ``pop + insert`` arithmetic itself."""

    def __init__(self, step: Step, row: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "step-card")
        self.setProperty("state", "idle")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        # Right-click context menu — adds "이 단계만 테스트" beside
        # the existing 복제/삭제 buttons. Custom signal-driven so the
        # host owns the actual run logic.
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._row = row
        self._step = step
        self._kind = _trigger_kind(step)
        self._drag_start = None
        self._hover = False
        # Painted entirely in our ``paintEvent`` — disable Qt's
        # built-in styled-background drawing so the QSS rule from
        # theme.py doesn't paint a frame underneath ours.
        self.setAttribute(Qt.WA_StyledBackground, False)
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
        self._apply_card_style()

    def set_error(self, error: bool, *, with_capture: bool = False) -> None:
        self.setProperty("state", "error" if error else "idle")
        # Surface the inline preview button only when we actually have a
        # cached image to show — otherwise the button is just noise.
        self._preview_btn.setVisible(error and with_capture)
        self._apply_card_style()

    def set_issues(self, issues: list[StepIssue]) -> None:
        """Populate the inline preflight badges. Pass ``[]`` to clear.

        Each chip carries the short ``label`` and a tooltip with the
        full ``detail`` sentence. Severity drives colour:
        error → rose ``error`` token, warning → brass ``primary`` token.
        """
        # Drop the previous chips before adding new ones — chip count
        # varies between calls so we re-build rather than diff.
        for w in self._issue_widgets:
            self._issue_row.removeWidget(w)
            w.deleteLater()
        self._issue_widgets.clear()

        for issue in issues:
            chip = QLabel(("⛔  " if issue.severity == "error" else "⚠  ") + issue.label)
            colour = C["error"] if issue.severity == "error" else C["primary"]
            bg = (
                "rgba(217, 132, 124, 0.12)"
                if issue.severity == "error"
                else "rgba(232, 178, 106, 0.12)"
            )
            chip.setStyleSheet(
                f"color: {colour}; background-color: {bg};"
                f"border: 1px solid {colour}; border-radius: 4px;"
                f"padding: 1px 6px; font-size: 10px; font-weight: 700;"
            )
            chip.setToolTip(issue.detail)
            self._issue_row.addWidget(chip)
            self._issue_widgets.append(chip)

        # The error border on the card itself only kicks in for errors,
        # not warnings (warnings are advisory). Don't overwrite the
        # 'active' / runtime-error state when the card is currently
        # selected.
        has_error = any(i.severity == "error" for i in issues)
        current = self.property("state")
        if current not in ("active", "error"):
            # idle → preflight-error is fine; error (runtime) wins.
            self.setProperty(
                "state", "error" if has_error else "idle",
            )
            self._apply_card_style()

    # --- assembly -------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        # Top inset matches the painted stripe height (3 px idle, 4 px
        # active) so child widgets never overlap the coloured band.
        # We intentionally leave the value at 4 — when the stripe
        # shrinks back to 3 in idle, the extra 1 px of top padding is
        # invisible and we avoid jiggling the body widgets on every
        # selection change.
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(0)

        # No stripe child widget — see the module-level comment.
        # The trigger-kind colour is drawn directly in ``paintEvent``
        # using the same QPainterPath as the card outline so the
        # corners share geometry to the pixel.

        body = QWidget(self)
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(10, 4, 6, 8)
        body_l.setSpacing(3)

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

        # Action buttons are icon-only so the card row stays narrow
        # enough for ~340 px wide step list panes. Each button has a
        # ``setToolTip`` carrying the long-form Korean label so the
        # affordance is still discoverable on hover.
        def _icon_btn(glyph: str, tip: str, role: str = "icon-mini") -> QPushButton:
            b = QPushButton(glyph)
            b.setProperty("role", role)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            b.setFixedWidth(26)
            return b

        # Hidden by default — toggled visible only when ``set_error(
        # error, with_capture=True)`` runs after the runner emits
        # failure_capture.
        self._preview_btn = _icon_btn(
            "📷",
            "마지막 실패 시 매크로가 본 화면 보기 — 영역/템플릿 조정에 도움이 돼요",
        )
        self._preview_btn.clicked.connect(
            lambda: self.preview_failure_requested.emit(self._row)
        )
        self._preview_btn.setVisible(False)
        top.addWidget(self._preview_btn)

        # Edit (✏), duplicate (⎘), delete (🗑) — the three card actions.
        # Double-clicking the card body also opens the editor, so the
        # ✏ button is the second-class affordance.
        self._edit_btn = _icon_btn("✏", "이 단계 편집 (더블클릭으로도 가능)")
        self._edit_btn.clicked.connect(
            lambda: self.edit_requested.emit(self._row)
        )
        top.addWidget(self._edit_btn)

        self._dup_btn = _icon_btn("⎘", "이 단계 복제")
        self._dup_btn.clicked.connect(
            lambda: self.duplicate_requested.emit(self._row)
        )
        top.addWidget(self._dup_btn)

        self._del_btn = _icon_btn("🗑", "이 단계 삭제", role="danger-ghost")
        self._del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._row)
        )
        top.addWidget(self._del_btn)

        body_l.addLayout(top)

        # --- trigger sentence (single line, elide) -----------------------
        self._trigger_lbl = QLabel()
        self._trigger_lbl.setStyleSheet(
            f"color: {C['on-surface']}; font-size: 13px; font-weight: 600;"
        )
        # Plain label — no text selection. Selectable text intercepts
        # double-clicks (turning them into "select word") which would
        # break the card-level double-click → edit dialog flow.
        self._trigger_lbl.setTextInteractionFlags(Qt.NoTextInteraction)
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

        # Inline preflight issue chips — populated by ``set_issues()``.
        # Hidden by default so the card height doesn't bounce on every
        # add. Lives below the action sentence so long Korean error
        # detail can wrap without squeezing the trigger summary.
        self._issue_row = QHBoxLayout()
        self._issue_row.setSpacing(4)
        self._issue_row.setContentsMargins(0, 2, 0, 0)
        self._issue_widgets: list[QLabel] = []
        body_l.addLayout(self._issue_row)

        layout.addWidget(body)

    def _refresh(self) -> None:
        kind = _trigger_kind(self._step)
        self._kind = kind

        self._badge.setProperty("badge", kind)
        self._badge.setText(_TRIGGER_LABEL[kind])
        self._apply_card_style()

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

    def _apply_card_style(self) -> None:
        """Trigger a repaint after a state / kind change.

        All visual decisions (background, stripe colour + height,
        outline colour) are made inside ``paintEvent``; this just
        marks the widget dirty and re-polishes the kind-coloured
        badge so theme.py's ``QLabel[badge=...]`` selector kicks in.
        """
        self.update()
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)

    # Backwards-compatible alias — older call sites used _reapply_style.
    _reapply_style = _apply_card_style

    # --- painting -------------------------------------------------------

    def enterEvent(self, event):  # noqa: N802 — Qt override
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 — Qt override
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):  # noqa: N802 — Qt override
        """Draw background + top stripe + outline in one antialiased
        pass so the stripe corners and the outline corners share
        geometry to the pixel (see module-level comment for why)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 0.5 px inset gives a crisp 1-pixel-wide stroke at integer
        # coordinates after antialiasing. Without it the outline
        # smears into a 2 px fuzzy line.
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 10.0

        state = self.property("state") or "idle"
        if state == "error":
            border_color = QColor(C["quaternary"])
            bg = QColor(C["surface-container"])
        elif state == "active":
            border_color = QColor(C["primary"])
            bg = QColor(C["surface-container-high"])
        else:
            border_color = QColor(C["outline-variant"])
            bg = QColor(
                C["surface-container-high"] if self._hover
                else C["surface-container"]
            )
        stripe_color = QColor(STRIPE.get(self._kind, C["outline"]))
        stripe_h = 4.0 if state == "active" else 3.0

        # 1) Card background — fully rounded.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, radius, radius)

        # 2) Top stripe — fill a band along the top, clipped to the
        #    card's rounded path so its top corners trace the same
        #    arc as the card outline. ``setClipPath`` accepts the
        #    very same path we'll stroke as the outline below, which
        #    is what guarantees pixel-level alignment.
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(path)
        painter.fillRect(
            QRectF(rect.x(), rect.y(), rect.width(), stripe_h),
            stripe_color,
        )
        painter.restore()

        # 3) Outline — drawn last so it sits on top of bg + stripe and
        #    closes both shapes with one continuous curve.
        pen = QPen(border_color)
        pen.setWidthF(1.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.end()

    # --- mouse selection + drag source ---------------------------------

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton:
            self.selected.emit(self._row)
            self._drag_start = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):  # noqa: N802
        if self._drag_start is None or not (e.buttons() & Qt.LeftButton):
            return super().mouseMoveEvent(e)
        delta = e.position().toPoint() - self._drag_start
        if delta.manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(e)

        # Begin drag — payload is the source row index.
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(STEP_DRAG_MIME, str(self._row).encode("utf-8"))
        drag.setMimeData(mime)
        # Carry a snapshot of the card itself as the drag pixmap so the
        # cursor visibly carries "the thing being moved".
        pix = self.grab()
        # Half-opacity so the user can see what's underneath.
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtGui import QPainter, QPixmap
        translucent = QPixmap(pix.size())
        translucent.fill(_Qt.transparent)
        p = QPainter(translucent)
        p.setOpacity(0.6)
        p.drawPixmap(0, 0, pix)
        p.end()
        drag.setPixmap(translucent)
        drag.setHotSpot(self._drag_start)
        drag.exec(Qt.MoveAction)
        self._drag_start = None

    def mouseReleaseEvent(self, e):  # noqa: N802
        self._drag_start = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):  # noqa: N802
        """Double-click anywhere on the card → open the editor.

        Buttons inside the card consume their own clicks before this
        handler runs, so double-clicking the 편집/복제/삭제 row stays
        unaffected — only the body opens the dialog."""
        if e.button() == Qt.LeftButton:
            self.edit_requested.emit(self._row)
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    # --- drop target ----------------------------------------------------

    def dragEnterEvent(self, e):  # noqa: N802
        if e.mimeData().hasFormat(STEP_DRAG_MIME):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):  # noqa: N802
        if e.mimeData().hasFormat(STEP_DRAG_MIME):
            e.acceptProposedAction()

    def dropEvent(self, e):  # noqa: N802
        if not e.mimeData().hasFormat(STEP_DRAG_MIME):
            return
        try:
            src = int(bytes(e.mimeData().data(STEP_DRAG_MIME)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        if src == self._row:
            return  # no-op: dropped onto self
        # If the cursor is in the upper half of this card, insert *before*;
        # bottom half, insert *after*. ``target`` is the index in the
        # *original* list where the source should land after a pop+insert.
        y = e.position().y()
        target = self._row if y < self.height() / 2 else self._row + 1
        self.reorder_requested.emit(src, target)
        e.acceptProposedAction()

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

    # --- context menu ---------------------------------------------------

    def _on_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        # The card emits ``selected`` first so the form switches to this
        # step before the action runs — feels less surprising than
        # running a step you can't see.
        self.selected.emit(self._row)

        act_test = QAction("▶  이 단계만 테스트", self)
        act_test.triggered.connect(lambda: self.test_requested.emit(self._row))
        menu.addAction(act_test)
        menu.addSeparator()
        act_dup = QAction("복제 (Ctrl+D)", self)
        act_dup.triggered.connect(lambda: self.duplicate_requested.emit(self._row))
        menu.addAction(act_dup)
        act_del = QAction("삭제", self)
        act_del.triggered.connect(lambda: self.delete_requested.emit(self._row))
        menu.addAction(act_del)
        menu.exec(self.mapToGlobal(pos))
