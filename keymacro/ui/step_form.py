"""Step editor form.

Renders one editable step (trigger + action + flow controls). Updates flow
both ways: when the user changes a field, :pyattr:`step_changed` is fired
with a fresh :class:`Step`; when the host wants to load a different step,
it calls :meth:`load_step`.
"""

from __future__ import annotations

from typing import Optional, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
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
    Region,
    ScheduleTrigger,
    Step,
    TimeTrigger,
    Trigger,
    TypeAction,
    WaitAction,
    WebClickAction,
    WebElementVisibleTrigger,
    WebNavigateAction,
    WebTypeAction,
    WebUrlTrigger,
)


_TRIGGER_TYPES = [
    "image", "time", "pixel",
    "web_element", "web_url", "hybrid_image",
    "ocr_text", "schedule",
]
_ACTION_TYPES = [
    "click", "key", "type", "drag", "wait",
    "web_click", "web_type", "web_navigate",
    "extract_text",
]

# Display labels — kept separate so the combo userData stays the schema key.
_TRIGGER_LABELS = {
    "image": "이미지가 보이면",
    "time": "일정 시간 뒤에",
    "pixel": "특정 색이 보이면",
    "web_element": "웹 요소가 보이면",
    "web_url": "URL이 일치하면",
    "hybrid_image": "이미지+URL (디버그 모드 X)",
    "ocr_text": "화면 텍스트가 보이면",
    "schedule": "예약 시각이 되면",
}
_ACTION_LABELS = {
    "click": "클릭한다",
    "key": "키를 누른다",
    "type": "텍스트를 입력한다",
    "drag": "드래그한다",
    "wait": "잠시 멈춘다",
    "web_click": "웹 요소를 클릭",
    "web_type": "웹 요소에 입력",
    "web_navigate": "URL로 이동",
    "extract_text": "텍스트 추출 → 변수",
}


def _bilingual_combo(pairs: list[tuple[str, str]]) -> QComboBox:
    """Build a QComboBox where the displayed text is Korean but the
    *userData* is the schema key. Read with ``.currentData()``, write
    with ``setCurrentIndex(findData(value))`` — never use
    ``currentText()`` / ``setCurrentText()`` on these or you'll feed the
    Korean label into Pydantic validation and crash.
    """
    cb = QComboBox()
    for key, label in pairs:
        cb.addItem(label, key)
    return cb


def _select_data(combo: QComboBox, value: str) -> None:
    """Move a bilingual combo to the row whose userData equals ``value``.
    No-op if not found (so loading legacy data with unknown values
    leaves the current selection intact)."""
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)


class StepForm(QWidget):
    step_changed = Signal()
    pick_region_requested = Signal()       # user clicked "pick region"
    capture_template_requested = Signal()  # user clicked "capture template"
    pick_web_selector_requested = Signal(str)
    """Emitted with one of {"we_selector","wc_selector","wt_selector"};
    handled by MainWindow which spawns a PickerThread."""

    def __init__(self) -> None:
        super().__init__()
        self._loading = False
        self._step: Optional[Step] = None
        self._build_ui()

    # ----------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(10)

        # General / flow group.
        general = QGroupBox("이 단계")
        gl = QFormLayout(general)
        gl.setLabelAlignment(Qt.AlignLeft)
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("단계 ID (영문, 다른 단계와 겹치지 않게)")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("이 단계가 무슨 일을 하는지 한 줄로")
        self.on_failure = _bilingual_combo([
            ("abort", "중단"),
            ("skip", "건너뛰기"),
            ("retry", "재시도"),
        ])
        self.retry_count = QSpinBox()
        self.retry_count.setRange(0, 100)
        self.repeat = QSpinBox()
        self.repeat.setRange(1, 1000)
        self.goto = QLineEdit()
        self.goto.setPlaceholderText("성공 시 점프할 다른 단계 ID (비우면 다음 단계로)")
        gl.addRow("ID", self.id_edit)
        gl.addRow("이름", self.name_edit)
        gl.addRow("실패하면?", self.on_failure)
        gl.addRow("재시도 횟수", self.retry_count)
        gl.addRow("이 단계 반복", self.repeat)
        gl.addRow("성공 시 다음 단계", self.goto)
        outer.addWidget(general)

        # Trigger group.
        trig_box = QGroupBox("언제 실행할까요?")
        tv = QVBoxLayout(trig_box)
        self.trigger_type = QComboBox()
        for key in _TRIGGER_TYPES:
            self.trigger_type.addItem(_TRIGGER_LABELS[key], key)
        tv.addWidget(self.trigger_type)
        self.trigger_stack = QStackedWidget()
        self._build_image_trigger_form()
        self._build_time_trigger_form()
        self._build_pixel_trigger_form()
        self._build_web_element_trigger_form()
        self._build_web_url_trigger_form()
        self._build_hybrid_image_trigger_form()
        self._build_ocr_trigger_form()
        self._build_schedule_trigger_form()
        tv.addWidget(self.trigger_stack)
        outer.addWidget(trig_box)

        # Action group.
        act_box = QGroupBox("어떻게 동작할까요?")
        av = QVBoxLayout(act_box)
        self.action_type = QComboBox()
        for key in _ACTION_TYPES:
            self.action_type.addItem(_ACTION_LABELS[key], key)
        av.addWidget(self.action_type)
        self.action_stack = QStackedWidget()
        self._build_click_form()
        self._build_key_form()
        self._build_type_form()
        self._build_drag_form()
        self._build_wait_form()
        self._build_web_click_form()
        self._build_web_type_form()
        self._build_web_navigate_form()
        self._build_extract_text_form()
        av.addWidget(self.action_stack)
        outer.addWidget(act_box)

        outer.addStretch()

        # Wire change signals after sub-forms exist.
        self.trigger_type.currentIndexChanged.connect(self.trigger_stack.setCurrentIndex)
        self.trigger_type.currentIndexChanged.connect(self._emit_changed)
        self.action_type.currentIndexChanged.connect(self.action_stack.setCurrentIndex)
        self.action_type.currentIndexChanged.connect(self._emit_changed)

        for w in (
            self.id_edit, self.name_edit, self.goto,
        ):
            w.editingFinished.connect(self._emit_changed)
        self.on_failure.currentIndexChanged.connect(self._emit_changed)
        self.retry_count.valueChanged.connect(self._emit_changed)
        self.repeat.valueChanged.connect(self._emit_changed)

    # --- trigger sub-forms ------------------------------------------------

    def _build_image_trigger_form(self) -> None:
        w = QWidget()
        f = QFormLayout(w)
        self.img_template = QLineEdit()
        self.img_template.setPlaceholderText("templates/예시.png")
        self.img_x = QSpinBox(); self.img_x.setRange(-100000, 100000)
        self.img_y = QSpinBox(); self.img_y.setRange(-100000, 100000)
        self.img_w = QSpinBox(); self.img_w.setRange(1, 100000); self.img_w.setValue(100)
        self.img_h = QSpinBox(); self.img_h.setRange(1, 100000); self.img_h.setValue(100)
        self.img_conf = QDoubleSpinBox(); self.img_conf.setRange(0.01, 1.0)
        self.img_conf.setSingleStep(0.05); self.img_conf.setValue(0.9)
        self.img_timeout = QDoubleSpinBox(); self.img_timeout.setRange(0.0, 3600.0); self.img_timeout.setValue(5.0)
        self.img_poll = QDoubleSpinBox(); self.img_poll.setRange(0.01, 60.0); self.img_poll.setSingleStep(0.05); self.img_poll.setValue(0.2)
        self.img_multi = QCheckBox("크기 변화에도 견디게 (다중 스케일)"); self.img_multi.setChecked(True)

        pick_btn = QPushButton("　🖍  화면에서 영역 그리기　")
        pick_btn.setProperty("role", "ghost")
        pick_btn.setCursor(Qt.PointingHandCursor)
        pick_btn.clicked.connect(self.pick_region_requested)
        cap_btn = QPushButton("　📸  지금 영역 화면 캡처　")
        cap_btn.setProperty("role", "primary")
        cap_btn.setCursor(Qt.PointingHandCursor)
        cap_btn.clicked.connect(self.capture_template_requested)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.addWidget(pick_btn)
        btn_row.addWidget(cap_btn)
        btn_row.addStretch()
        btn_wrap = QWidget(); btn_wrap.setLayout(btn_row)

        f.addRow("어떤 이미지?", self.img_template)
        f.addRow("영역 X", self.img_x)
        f.addRow("영역 Y", self.img_y)
        f.addRow("영역 너비", self.img_w)
        f.addRow("영역 높이", self.img_h)
        f.addRow("일치 정확도 (0.5~1.0)", self.img_conf)
        f.addRow("최대 대기 (초)", self.img_timeout)
        f.addRow("확인 주기 (초)", self.img_poll)
        f.addRow("", self.img_multi)
        f.addRow("", btn_wrap)

        for editor in (self.img_template,):
            editor.editingFinished.connect(self._emit_changed)
        for sp in (self.img_x, self.img_y, self.img_w, self.img_h):
            sp.valueChanged.connect(self._emit_changed)
        for dsp in (self.img_conf, self.img_timeout, self.img_poll):
            dsp.valueChanged.connect(self._emit_changed)
        self.img_multi.toggled.connect(self._emit_changed)

        self.trigger_stack.addWidget(w)

    def _build_time_trigger_form(self) -> None:
        w = QWidget()
        f = QFormLayout(w)
        self.time_delay = QDoubleSpinBox(); self.time_delay.setRange(0.0, 3600.0); self.time_delay.setSingleStep(0.1)
        self.time_delay.valueChanged.connect(self._emit_changed)
        f.addRow("기다릴 시간 (초)", self.time_delay)
        self.trigger_stack.addWidget(w)

    def _build_pixel_trigger_form(self) -> None:
        w = QWidget()
        f = QFormLayout(w)
        self.pix_x = QSpinBox(); self.pix_x.setRange(-100000, 100000)
        self.pix_y = QSpinBox(); self.pix_y.setRange(-100000, 100000)
        self.pix_r = QSpinBox(); self.pix_r.setRange(0, 255)
        self.pix_g = QSpinBox(); self.pix_g.setRange(0, 255)
        self.pix_b = QSpinBox(); self.pix_b.setRange(0, 255)
        self.pix_tol = QSpinBox(); self.pix_tol.setRange(0, 255); self.pix_tol.setValue(10)
        self.pix_timeout = QDoubleSpinBox(); self.pix_timeout.setRange(0.0, 3600.0); self.pix_timeout.setValue(5.0)
        self.pix_poll = QDoubleSpinBox(); self.pix_poll.setRange(0.01, 60.0); self.pix_poll.setSingleStep(0.05); self.pix_poll.setValue(0.2)
        for sp in (self.pix_x, self.pix_y, self.pix_r, self.pix_g, self.pix_b, self.pix_tol):
            sp.valueChanged.connect(self._emit_changed)
        for dsp in (self.pix_timeout, self.pix_poll):
            dsp.valueChanged.connect(self._emit_changed)
        f.addRow("위치 X", self.pix_x); f.addRow("위치 Y", self.pix_y)
        f.addRow("빨강 (R)", self.pix_r)
        f.addRow("초록 (G)", self.pix_g)
        f.addRow("파랑 (B)", self.pix_b)
        f.addRow("색 허용 오차", self.pix_tol)
        f.addRow("최대 대기 (초)", self.pix_timeout)
        f.addRow("확인 주기 (초)", self.pix_poll)
        self.trigger_stack.addWidget(w)

    # --- action sub-forms -------------------------------------------------

    def _build_click_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.click_x = QSpinBox(); self.click_x.setRange(-100000, 100000)
        self.click_y = QSpinBox(); self.click_y.setRange(-100000, 100000)
        self.click_btn = _bilingual_combo([
            ("left", "왼쪽"), ("right", "오른쪽"), ("middle", "가운데"),
        ])
        self.click_double = QCheckBox("더블클릭")
        self.click_relative = QCheckBox("매칭된 위치 기준 (이미지 트리거일 때)")
        self.click_input = _bilingual_combo([
            ("normal", "보통 (대부분의 앱)"),
            ("raw", "저수준 (게임/에뮬레이터)"),
        ])
        for sp in (self.click_x, self.click_y):
            sp.valueChanged.connect(self._emit_changed)
        for cb in (self.click_btn, self.click_input):
            cb.currentIndexChanged.connect(self._emit_changed)
        for chk in (self.click_double, self.click_relative):
            chk.toggled.connect(self._emit_changed)
        f.addRow("위치 X", self.click_x); f.addRow("위치 Y", self.click_y)
        f.addRow("어느 버튼?", self.click_btn)
        f.addRow("", self.click_double); f.addRow("", self.click_relative)
        f.addRow("입력 방식", self.click_input)
        self.action_stack.addWidget(w)

    def _build_key_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.key_keys = QLineEdit()
        self.key_keys.setPlaceholderText("예: ctrl+c, enter, f5, alt+tab")
        self.key_input = _bilingual_combo([
            ("normal", "보통 (대부분의 앱)"),
            ("raw", "저수준 (게임/에뮬레이터)"),
        ])
        self.key_keys.editingFinished.connect(self._emit_changed)
        self.key_input.currentIndexChanged.connect(self._emit_changed)
        f.addRow("어떤 키?", self.key_keys)
        f.addRow("입력 방식", self.key_input)
        self.action_stack.addWidget(w)

    def _build_type_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.type_text = QLineEdit()
        self.type_interval = QDoubleSpinBox(); self.type_interval.setRange(0.0, 5.0); self.type_interval.setSingleStep(0.01)
        self.type_text.editingFinished.connect(self._emit_changed)
        self.type_interval.valueChanged.connect(self._emit_changed)
        self.type_text.setPlaceholderText("예: 안녕하세요")
        f.addRow("입력할 텍스트", self.type_text)
        f.addRow("글자 사이 간격 (초)", self.type_interval)
        self.action_stack.addWidget(w)

    def _build_drag_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.drag_x1 = QSpinBox(); self.drag_x1.setRange(-100000, 100000)
        self.drag_y1 = QSpinBox(); self.drag_y1.setRange(-100000, 100000)
        self.drag_x2 = QSpinBox(); self.drag_x2.setRange(-100000, 100000)
        self.drag_y2 = QSpinBox(); self.drag_y2.setRange(-100000, 100000)
        self.drag_dur = QDoubleSpinBox(); self.drag_dur.setRange(0.0, 60.0); self.drag_dur.setValue(0.3)
        self.drag_btn = _bilingual_combo([
            ("left", "왼쪽"), ("right", "오른쪽"), ("middle", "가운데"),
        ])
        for sp in (self.drag_x1, self.drag_y1, self.drag_x2, self.drag_y2):
            sp.valueChanged.connect(self._emit_changed)
        self.drag_dur.valueChanged.connect(self._emit_changed)
        self.drag_btn.currentIndexChanged.connect(self._emit_changed)
        f.addRow("시작 X", self.drag_x1); f.addRow("시작 Y", self.drag_y1)
        f.addRow("끝 X", self.drag_x2); f.addRow("끝 Y", self.drag_y2)
        f.addRow("드래그 시간 (초)", self.drag_dur)
        f.addRow("어느 버튼?", self.drag_btn)
        self.action_stack.addWidget(w)

    def _build_wait_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.wait_dur = QDoubleSpinBox(); self.wait_dur.setRange(0.0, 3600.0); self.wait_dur.setSingleStep(0.1)
        self.wait_dur.valueChanged.connect(self._emit_changed)
        f.addRow("멈출 시간 (초)", self.wait_dur)
        self.action_stack.addWidget(w)

    # --- web sub-forms ----------------------------------------------------

    def _make_pick_button(self, field_key: str) -> QPushButton:
        btn = QPushButton("　🎯  화면에서 요소 고르기　")
        btn.setProperty("role", "ghost")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Chrome 페이지로 가서 클릭으로 셀렉터 자동 추출 (Esc 취소)")
        btn.clicked.connect(
            lambda: self.pick_web_selector_requested.emit(field_key)
        )
        return btn

    def _build_web_element_trigger_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.we_selector = QLineEdit()
        self.we_selector.setPlaceholderText("예: role=button[name=\"학습하기\"]  또는  #submit-btn")
        self.we_url_contains = QLineEdit()
        self.we_url_contains.setPlaceholderText("선택 — 이 문자열을 포함한 URL에서만 동작")
        self.we_state = _bilingual_combo([
            ("visible", "보임 (visible)"),
            ("attached", "DOM에 존재 (attached)"),
            ("hidden", "안 보임 (hidden)"),
            ("detached", "DOM에서 사라짐 (detached)"),
        ])
        self.we_timeout = QDoubleSpinBox(); self.we_timeout.setRange(0.0, 3600.0); self.we_timeout.setValue(10.0)
        self.we_poll = QDoubleSpinBox(); self.we_poll.setRange(0.05, 60.0); self.we_poll.setValue(0.3)
        for ed in (self.we_selector, self.we_url_contains):
            ed.editingFinished.connect(self._emit_changed)
        self.we_state.currentIndexChanged.connect(self._emit_changed)
        for sp in (self.we_timeout, self.we_poll):
            sp.valueChanged.connect(self._emit_changed)
        f.addRow("어떤 요소? (셀렉터)", self.we_selector)
        f.addRow("", self._make_pick_button("we_selector"))
        f.addRow("이 URL일 때만 (선택)", self.we_url_contains)
        f.addRow("어떤 상태?", self.we_state)
        f.addRow("최대 대기 (초)", self.we_timeout)
        f.addRow("확인 주기 (초)", self.we_poll)
        self.trigger_stack.addWidget(w)

    def _build_web_url_trigger_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.wu_pattern = QLineEdit()
        self.wu_pattern.setPlaceholderText("예: /lec/.../complete 또는 example.com")
        self.wu_mode = _bilingual_combo([
            ("contains", "포함 (contains)"),
            ("regex", "정규식 (regex)"),
            ("exact", "정확히 일치 (exact)"),
        ])
        self.wu_timeout = QDoubleSpinBox(); self.wu_timeout.setRange(0.0, 3600.0); self.wu_timeout.setValue(10.0)
        self.wu_poll = QDoubleSpinBox(); self.wu_poll.setRange(0.05, 60.0); self.wu_poll.setValue(0.3)
        self.wu_pattern.editingFinished.connect(self._emit_changed)
        self.wu_mode.currentIndexChanged.connect(self._emit_changed)
        for sp in (self.wu_timeout, self.wu_poll):
            sp.valueChanged.connect(self._emit_changed)
        f.addRow("URL 패턴", self.wu_pattern)
        f.addRow("매칭 방식", self.wu_mode)
        f.addRow("최대 대기 (초)", self.wu_timeout)
        f.addRow("확인 주기 (초)", self.wu_poll)
        self.trigger_stack.addWidget(w)

    def _build_hybrid_image_trigger_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.hi_template = QLineEdit()
        self.hi_template.setPlaceholderText("templates/예시.png")
        self.hi_x = QSpinBox(); self.hi_x.setRange(-100000, 100000)
        self.hi_y = QSpinBox(); self.hi_y.setRange(-100000, 100000)
        self.hi_w = QSpinBox(); self.hi_w.setRange(1, 100000); self.hi_w.setValue(400)
        self.hi_h = QSpinBox(); self.hi_h.setRange(1, 100000); self.hi_h.setValue(300)
        self.hi_url = QLineEdit()
        self.hi_url.setPlaceholderText("예: sela.yuhs.ac/lec  또는  /lec/.+/complete")
        self.hi_url_mode = QComboBox()
        self.hi_url_mode.addItem("포함 (contains)", "contains")
        self.hi_url_mode.addItem("정규식 (regex)", "regex")
        self.hi_url_mode.addItem("정확히 일치 (exact)", "exact")
        self.hi_browser = QComboBox()
        self.hi_browser.addItem("아무 브라우저", "any")
        self.hi_browser.addItem("Chrome", "chrome")
        self.hi_browser.addItem("Edge", "edge")
        self.hi_browser.addItem("Firefox", "firefox")
        self.hi_conf = QDoubleSpinBox(); self.hi_conf.setRange(0.01, 1.0); self.hi_conf.setValue(0.9); self.hi_conf.setSingleStep(0.05)
        self.hi_timeout = QDoubleSpinBox(); self.hi_timeout.setRange(0.0, 3600.0); self.hi_timeout.setValue(10.0)
        self.hi_poll = QDoubleSpinBox(); self.hi_poll.setRange(0.05, 60.0); self.hi_poll.setValue(0.3)
        self.hi_multi = QCheckBox("크기 변화에도 견디게 (다중 스케일)"); self.hi_multi.setChecked(True)

        for ed in (self.hi_template, self.hi_url):
            ed.editingFinished.connect(self._emit_changed)
        for sp in (self.hi_x, self.hi_y, self.hi_w, self.hi_h):
            sp.valueChanged.connect(self._emit_changed)
        for dsp in (self.hi_conf, self.hi_timeout, self.hi_poll):
            dsp.valueChanged.connect(self._emit_changed)
        for cb in (self.hi_url_mode, self.hi_browser):
            cb.currentIndexChanged.connect(self._emit_changed)
        self.hi_multi.toggled.connect(self._emit_changed)

        pick_btn = QPushButton("　🖍  화면에서 영역 그리기　")
        pick_btn.setProperty("role", "ghost")
        pick_btn.setCursor(Qt.PointingHandCursor)
        pick_btn.clicked.connect(self.pick_region_requested)
        cap_btn = QPushButton("　📸  지금 영역 화면 캡처　")
        cap_btn.setProperty("role", "primary")
        cap_btn.setCursor(Qt.PointingHandCursor)
        cap_btn.clicked.connect(self.capture_template_requested)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.addWidget(pick_btn)
        btn_row.addWidget(cap_btn)
        btn_row.addStretch()
        btn_wrap = QWidget(); btn_wrap.setLayout(btn_row)

        f.addRow("어떤 이미지?", self.hi_template)
        f.addRow("영역 X", self.hi_x)
        f.addRow("영역 Y", self.hi_y)
        f.addRow("영역 너비", self.hi_w)
        f.addRow("영역 높이", self.hi_h)
        f.addRow("URL 패턴", self.hi_url)
        f.addRow("URL 매칭 방식", self.hi_url_mode)
        f.addRow("어떤 브라우저?", self.hi_browser)
        f.addRow("일치 정확도 (0.5~1.0)", self.hi_conf)
        f.addRow("최대 대기 (초)", self.hi_timeout)
        f.addRow("확인 주기 (초)", self.hi_poll)
        f.addRow("", self.hi_multi)
        f.addRow("", btn_wrap)
        self.trigger_stack.addWidget(w)

    def _build_ocr_trigger_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.ocr_text = QLineEdit()
        self.ocr_text.setPlaceholderText("예: 다음, 학습완료, OTP, \\d{6}")
        self.ocr_x = QSpinBox(); self.ocr_x.setRange(-100000, 100000)
        self.ocr_y = QSpinBox(); self.ocr_y.setRange(-100000, 100000)
        self.ocr_w = QSpinBox(); self.ocr_w.setRange(1, 100000); self.ocr_w.setValue(400)
        self.ocr_h = QSpinBox(); self.ocr_h.setRange(1, 100000); self.ocr_h.setValue(120)
        self.ocr_mode = QComboBox()
        self.ocr_mode.addItem("포함 (contains)", "contains")
        self.ocr_mode.addItem("정규식 (regex)", "regex")
        self.ocr_mode.addItem("정확히 일치 (exact)", "exact")
        self.ocr_lang = QComboBox()
        for label, key in (("한+영", "kor+eng"), ("한", "kor"), ("영", "eng"),
                           ("일", "jpn"), ("중간", "chi_sim"), ("중번", "chi_tra")):
            self.ocr_lang.addItem(label, key)
        self.ocr_case = QCheckBox("대소문자 구분")
        self.ocr_timeout = QDoubleSpinBox(); self.ocr_timeout.setRange(0.0, 86400.0); self.ocr_timeout.setValue(30.0)
        self.ocr_poll = QDoubleSpinBox(); self.ocr_poll.setRange(0.1, 60.0); self.ocr_poll.setValue(1.0)
        for ed in (self.ocr_text,):
            ed.editingFinished.connect(self._emit_changed)
        for sp in (self.ocr_x, self.ocr_y, self.ocr_w, self.ocr_h):
            sp.valueChanged.connect(self._emit_changed)
        for cb in (self.ocr_mode, self.ocr_lang):
            cb.currentIndexChanged.connect(self._emit_changed)
        for dsp in (self.ocr_timeout, self.ocr_poll):
            dsp.valueChanged.connect(self._emit_changed)
        self.ocr_case.toggled.connect(self._emit_changed)

        pick_btn = QPushButton("　🖍  영역 그리기　")
        pick_btn.setProperty("role", "ghost")
        pick_btn.setCursor(Qt.PointingHandCursor)
        pick_btn.clicked.connect(self.pick_region_requested)

        f.addRow("어떤 텍스트?", self.ocr_text)
        f.addRow("영역 X", self.ocr_x); f.addRow("영역 Y", self.ocr_y)
        f.addRow("영역 너비", self.ocr_w); f.addRow("영역 높이", self.ocr_h)
        f.addRow("매칭 방식", self.ocr_mode)
        f.addRow("언어", self.ocr_lang)
        f.addRow("", self.ocr_case)
        f.addRow("최대 대기 (초)", self.ocr_timeout)
        f.addRow("확인 주기 (초)", self.ocr_poll)
        f.addRow("", pick_btn)
        self.trigger_stack.addWidget(w)

    def _build_schedule_trigger_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.sch_at = QLineEdit("09:00")
        self.sch_at.setPlaceholderText("HH:MM (24시 형식)")
        # Weekday checkboxes
        self.sch_days: list[QCheckBox] = []
        days_row = QHBoxLayout()
        days_row.setSpacing(4)
        for label in ("월", "화", "수", "목", "금", "토", "일"):
            cb = QCheckBox(label)
            cb.toggled.connect(self._emit_changed)
            days_row.addWidget(cb)
            self.sch_days.append(cb)
        days_wrap = QWidget(); days_wrap.setLayout(days_row)
        # Default: Mon..Fri checked
        for i in range(5):
            self.sch_days[i].setChecked(True)
        self.sch_grace = QDoubleSpinBox(); self.sch_grace.setRange(0.0, 3600.0); self.sch_grace.setValue(60.0)

        self.sch_at.editingFinished.connect(self._emit_changed)
        self.sch_grace.valueChanged.connect(self._emit_changed)

        f.addRow("시각 (HH:MM)", self.sch_at)
        f.addRow("요일", days_wrap)
        f.addRow("늦어도 허용 (초)", self.sch_grace)
        self.trigger_stack.addWidget(w)

    def _build_extract_text_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.ext_var = QLineEdit("otp")
        self.ext_var.setPlaceholderText("변수명 (영문/숫자/_, 예: otp, name, email_addr)")
        self.ext_x = QSpinBox(); self.ext_x.setRange(-100000, 100000)
        self.ext_y = QSpinBox(); self.ext_y.setRange(-100000, 100000)
        self.ext_w = QSpinBox(); self.ext_w.setRange(1, 100000); self.ext_w.setValue(400)
        self.ext_h = QSpinBox(); self.ext_h.setRange(1, 100000); self.ext_h.setValue(80)
        self.ext_lang = QComboBox()
        for label, key in (("한+영", "kor+eng"), ("한", "kor"), ("영", "eng")):
            self.ext_lang.addItem(label, key)
        self.ext_strip = QCheckBox("앞/뒤/내부 공백 정리"); self.ext_strip.setChecked(True)

        self.ext_var.editingFinished.connect(self._emit_changed)
        for sp in (self.ext_x, self.ext_y, self.ext_w, self.ext_h):
            sp.valueChanged.connect(self._emit_changed)
        self.ext_lang.currentIndexChanged.connect(self._emit_changed)
        self.ext_strip.toggled.connect(self._emit_changed)

        f.addRow("저장할 변수 이름", self.ext_var)
        f.addRow("영역 X", self.ext_x); f.addRow("영역 Y", self.ext_y)
        f.addRow("영역 너비", self.ext_w); f.addRow("영역 높이", self.ext_h)
        f.addRow("언어", self.ext_lang)
        f.addRow("", self.ext_strip)
        self.action_stack.addWidget(w)

    def _build_web_click_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.wc_selector = QLineEdit()
        self.wc_selector.setPlaceholderText("예: role=button[name=\"학습하기\"]")
        self.wc_button = _bilingual_combo([
            ("left", "왼쪽"), ("right", "오른쪽"), ("middle", "가운데"),
        ])
        self.wc_double = QCheckBox("더블클릭")
        self.wc_force = QCheckBox("강제 클릭 (보이지 않아도)")
        self.wc_selector.editingFinished.connect(self._emit_changed)
        self.wc_button.currentIndexChanged.connect(self._emit_changed)
        for chk in (self.wc_double, self.wc_force):
            chk.toggled.connect(self._emit_changed)
        f.addRow("어떤 요소? (셀렉터)", self.wc_selector)
        f.addRow("", self._make_pick_button("wc_selector"))
        f.addRow("어느 버튼?", self.wc_button)
        f.addRow("", self.wc_double)
        f.addRow("", self.wc_force)
        self.action_stack.addWidget(w)

    def _build_web_type_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.wt_selector = QLineEdit()
        self.wt_selector.setPlaceholderText("예: input[name='username']")
        self.wt_text = QLineEdit()
        self.wt_text.setPlaceholderText("입력할 텍스트")
        self.wt_delay = QSpinBox(); self.wt_delay.setRange(0, 1000); self.wt_delay.setSuffix(" ms")
        for ed in (self.wt_selector, self.wt_text):
            ed.editingFinished.connect(self._emit_changed)
        self.wt_delay.valueChanged.connect(self._emit_changed)
        f.addRow("어떤 입력란? (셀렉터)", self.wt_selector)
        f.addRow("", self._make_pick_button("wt_selector"))
        f.addRow("입력할 텍스트", self.wt_text)
        f.addRow("타이핑 간격", self.wt_delay)
        self.action_stack.addWidget(w)

    def _build_web_navigate_form(self) -> None:
        w = QWidget(); f = QFormLayout(w)
        self.wn_url = QLineEdit()
        self.wn_url.setPlaceholderText("https://...")
        self.wn_wait = _bilingual_combo([
            ("load", "load (모든 리소스 로드)"),
            ("domcontentloaded", "domcontentloaded (DOM 준비)"),
            ("networkidle", "networkidle (네트워크 고요)"),
            ("commit", "commit (URL만 바뀜)"),
        ])
        self.wn_url.editingFinished.connect(self._emit_changed)
        self.wn_wait.currentIndexChanged.connect(self._emit_changed)
        f.addRow("이동할 URL", self.wn_url)
        f.addRow("어디까지 기다릴까", self.wn_wait)
        self.action_stack.addWidget(w)

    # ----------------------------------------------------------------------

    def _emit_changed(self) -> None:
        if self._loading:
            return
        self.step_changed.emit()

    # --- public API -------------------------------------------------------

    def load_step(self, step: Step) -> None:
        self._loading = True
        try:
            self._step = step
            self.id_edit.setText(step.id)
            self.name_edit.setText(step.name)
            _select_data(self.on_failure, step.on_failure)
            self.retry_count.setValue(step.retry_count)
            self.repeat.setValue(step.repeat)
            self.goto.setText(step.on_success_goto or "")

            self._load_trigger(step.trigger)
            self._load_action(step.action)
        finally:
            self._loading = False

    def _load_trigger(self, trig: Trigger) -> None:
        if isinstance(trig, ImageTrigger):
            self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("image"))
            self.trigger_stack.setCurrentIndex(0)
            self.img_template.setText(trig.template)
            self.img_x.setValue(trig.region.x)
            self.img_y.setValue(trig.region.y)
            self.img_w.setValue(trig.region.w)
            self.img_h.setValue(trig.region.h)
            self.img_conf.setValue(trig.confidence)
            self.img_timeout.setValue(trig.timeout_s)
            self.img_poll.setValue(trig.poll_interval_s)
            self.img_multi.setChecked(trig.multi_scale)
        elif isinstance(trig, TimeTrigger):
            self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("time"))
            self.trigger_stack.setCurrentIndex(1)
            self.time_delay.setValue(trig.delay_s)
        elif isinstance(trig, PixelColorTrigger):
            self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("pixel"))
            self.trigger_stack.setCurrentIndex(2)
            self.pix_x.setValue(trig.x); self.pix_y.setValue(trig.y)
            self.pix_r.setValue(trig.rgb[0])
            self.pix_g.setValue(trig.rgb[1])
            self.pix_b.setValue(trig.rgb[2])
            self.pix_tol.setValue(trig.tolerance)
            self.pix_timeout.setValue(trig.timeout_s)
            self.pix_poll.setValue(trig.poll_interval_s)
        elif isinstance(trig, WebElementVisibleTrigger):
            self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("web_element"))
            self.trigger_stack.setCurrentIndex(3)
            self.we_selector.setText(trig.selector)
            self.we_url_contains.setText(trig.url_contains or "")
            _select_data(self.we_state, trig.state)
            self.we_timeout.setValue(trig.timeout_s)
            self.we_poll.setValue(trig.poll_interval_s)
        elif isinstance(trig, WebUrlTrigger):
            self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("web_url"))
            self.trigger_stack.setCurrentIndex(4)
            self.wu_pattern.setText(trig.pattern)
            _select_data(self.wu_mode, trig.mode)
            self.wu_timeout.setValue(trig.timeout_s)
            self.wu_poll.setValue(trig.poll_interval_s)
        elif isinstance(trig, HybridImageTrigger):
            self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("hybrid_image"))
            self.trigger_stack.setCurrentIndex(_TRIGGER_TYPES.index("hybrid_image"))
            self.hi_template.setText(trig.template)
            self.hi_x.setValue(trig.region.x); self.hi_y.setValue(trig.region.y)
            self.hi_w.setValue(trig.region.w); self.hi_h.setValue(trig.region.h)
            self.hi_url.setText(trig.url_contains)
            idx = self.hi_url_mode.findData(trig.url_mode)
            if idx >= 0: self.hi_url_mode.setCurrentIndex(idx)
            idx = self.hi_browser.findData(trig.browser)
            if idx >= 0: self.hi_browser.setCurrentIndex(idx)
            self.hi_conf.setValue(trig.confidence)
            self.hi_timeout.setValue(trig.timeout_s)
            self.hi_poll.setValue(trig.poll_interval_s)
            self.hi_multi.setChecked(trig.multi_scale)
        elif isinstance(trig, OcrTextTrigger):
            self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("ocr_text"))
            self.trigger_stack.setCurrentIndex(_TRIGGER_TYPES.index("ocr_text"))
            self.ocr_text.setText(trig.text)
            self.ocr_x.setValue(trig.region.x); self.ocr_y.setValue(trig.region.y)
            self.ocr_w.setValue(trig.region.w); self.ocr_h.setValue(trig.region.h)
            idx = self.ocr_mode.findData(trig.mode)
            if idx >= 0: self.ocr_mode.setCurrentIndex(idx)
            idx = self.ocr_lang.findData(trig.language)
            if idx >= 0: self.ocr_lang.setCurrentIndex(idx)
            self.ocr_case.setChecked(trig.case_sensitive)
            self.ocr_timeout.setValue(trig.timeout_s)
            self.ocr_poll.setValue(trig.poll_interval_s)
        elif isinstance(trig, ScheduleTrigger):
            self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("schedule"))
            self.trigger_stack.setCurrentIndex(_TRIGGER_TYPES.index("schedule"))
            self.sch_at.setText(trig.at)
            for i, cb in enumerate(self.sch_days):
                cb.setChecked(i in trig.weekdays)
            self.sch_grace.setValue(trig.grace_s)

    def _load_action(self, act: Action) -> None:
        if isinstance(act, ClickAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("click")); self.action_stack.setCurrentIndex(0)
            self.click_x.setValue(act.x); self.click_y.setValue(act.y)
            _select_data(self.click_btn, act.button)
            self.click_double.setChecked(act.double)
            self.click_relative.setChecked(act.relative_to_match)
            _select_data(self.click_input, act.input_mode)
        elif isinstance(act, KeyAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("key")); self.action_stack.setCurrentIndex(1)
            self.key_keys.setText(act.keys)
            _select_data(self.key_input, act.input_mode)
        elif isinstance(act, TypeAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("type")); self.action_stack.setCurrentIndex(2)
            self.type_text.setText(act.text)
            self.type_interval.setValue(act.interval_s)
        elif isinstance(act, DragAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("drag")); self.action_stack.setCurrentIndex(3)
            self.drag_x1.setValue(act.x1); self.drag_y1.setValue(act.y1)
            self.drag_x2.setValue(act.x2); self.drag_y2.setValue(act.y2)
            self.drag_dur.setValue(act.duration_s)
            _select_data(self.drag_btn, act.button)
        elif isinstance(act, WaitAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("wait")); self.action_stack.setCurrentIndex(4)
            self.wait_dur.setValue(act.duration_s)
        elif isinstance(act, WebClickAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("web_click")); self.action_stack.setCurrentIndex(5)
            self.wc_selector.setText(act.selector)
            _select_data(self.wc_button, act.button)
            self.wc_double.setChecked(act.double)
            self.wc_force.setChecked(act.force)
        elif isinstance(act, WebTypeAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("web_type")); self.action_stack.setCurrentIndex(6)
            self.wt_selector.setText(act.selector)
            self.wt_text.setText(act.text)
            self.wt_delay.setValue(act.delay_ms)
        elif isinstance(act, WebNavigateAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("web_navigate")); self.action_stack.setCurrentIndex(_ACTION_TYPES.index("web_navigate"))
            self.wn_url.setText(act.url)
            _select_data(self.wn_wait, act.wait_until)
        elif isinstance(act, ExtractTextAction):
            self.action_type.setCurrentIndex(_ACTION_TYPES.index("extract_text"))
            self.action_stack.setCurrentIndex(_ACTION_TYPES.index("extract_text"))
            self.ext_var.setText(act.variable)
            self.ext_x.setValue(act.region.x); self.ext_y.setValue(act.region.y)
            self.ext_w.setValue(act.region.w); self.ext_h.setValue(act.region.h)
            idx = self.ext_lang.findData(act.language)
            if idx >= 0: self.ext_lang.setCurrentIndex(idx)
            self.ext_strip.setChecked(act.strip)

    # --- snapshot -> Step --------------------------------------------------

    def to_step(self) -> Step:
        """Build a fresh :class:`Step` from the current widget values."""
        trig = self._build_trigger()
        act = self._build_action()
        return Step(
            id=self.id_edit.text().strip() or "step",
            name=self.name_edit.text(),
            trigger=trig,
            action=act,
            on_failure=cast("str", self.on_failure.currentData() or "abort"),
            retry_count=self.retry_count.value(),
            repeat=self.repeat.value(),
            on_success_goto=(self.goto.text().strip() or None),
        )

    def _build_trigger(self) -> Trigger:
        kind = self.trigger_type.currentData() or "image"
        if kind == "image":
            return ImageTrigger(
                template=self.img_template.text() or "template.png",
                region=Region(
                    x=self.img_x.value(), y=self.img_y.value(),
                    w=max(1, self.img_w.value()), h=max(1, self.img_h.value()),
                ),
                confidence=self.img_conf.value(),
                timeout_s=self.img_timeout.value(),
                poll_interval_s=self.img_poll.value(),
                multi_scale=self.img_multi.isChecked(),
            )
        if kind == "time":
            return TimeTrigger(delay_s=self.time_delay.value())
        if kind == "pixel":
            return PixelColorTrigger(
                x=self.pix_x.value(), y=self.pix_y.value(),
                rgb=(self.pix_r.value(), self.pix_g.value(), self.pix_b.value()),
                tolerance=self.pix_tol.value(),
                timeout_s=self.pix_timeout.value(),
                poll_interval_s=self.pix_poll.value(),
            )
        if kind == "web_element":
            return WebElementVisibleTrigger(
                selector=self.we_selector.text() or "body",
                url_contains=(self.we_url_contains.text().strip() or None),
                state=cast("str", self.we_state.currentData() or "visible"),
                timeout_s=self.we_timeout.value(),
                poll_interval_s=self.we_poll.value(),
            )
        if kind == "web_url":
            return WebUrlTrigger(
                pattern=self.wu_pattern.text() or "https://",
                mode=cast("str", self.wu_mode.currentData() or "contains"),
                timeout_s=self.wu_timeout.value(),
                poll_interval_s=self.wu_poll.value(),
            )
        if kind == "hybrid_image":
            return HybridImageTrigger(
                template=self.hi_template.text() or "template.png",
                region=Region(
                    x=self.hi_x.value(), y=self.hi_y.value(),
                    w=max(1, self.hi_w.value()), h=max(1, self.hi_h.value()),
                ),
                url_contains=self.hi_url.text() or "https://",
                url_mode=cast("str", self.hi_url_mode.currentData() or "contains"),
                browser=cast("str", self.hi_browser.currentData() or "any"),
                confidence=self.hi_conf.value(),
                timeout_s=self.hi_timeout.value(),
                poll_interval_s=self.hi_poll.value(),
                multi_scale=self.hi_multi.isChecked(),
            )
        if kind == "ocr_text":
            return OcrTextTrigger(
                text=self.ocr_text.text() or "텍스트",
                region=Region(
                    x=self.ocr_x.value(), y=self.ocr_y.value(),
                    w=max(1, self.ocr_w.value()), h=max(1, self.ocr_h.value()),
                ),
                mode=cast("str", self.ocr_mode.currentData() or "contains"),
                language=cast("str", self.ocr_lang.currentData() or "kor+eng"),
                case_sensitive=self.ocr_case.isChecked(),
                timeout_s=self.ocr_timeout.value(),
                poll_interval_s=self.ocr_poll.value(),
            )
        # schedule
        days = [i for i, cb in enumerate(self.sch_days) if cb.isChecked()] or [0]
        return ScheduleTrigger(
            at=self.sch_at.text() or "09:00",
            weekdays=days,
            grace_s=self.sch_grace.value(),
        )

    def _build_action(self) -> Action:
        kind = self.action_type.currentData() or "click"
        if kind == "click":
            return ClickAction(
                x=self.click_x.value(), y=self.click_y.value(),
                button=cast("str", self.click_btn.currentData() or "left"),
                double=self.click_double.isChecked(),
                relative_to_match=self.click_relative.isChecked(),
                input_mode=cast("str", self.click_input.currentData() or "normal"),
            )
        if kind == "key":
            return KeyAction(
                keys=self.key_keys.text() or "enter",
                input_mode=cast("str", self.key_input.currentData() or "normal"),
            )
        if kind == "type":
            return TypeAction(
                text=self.type_text.text(),
                interval_s=self.type_interval.value(),
            )
        if kind == "drag":
            return DragAction(
                x1=self.drag_x1.value(), y1=self.drag_y1.value(),
                x2=self.drag_x2.value(), y2=self.drag_y2.value(),
                duration_s=self.drag_dur.value(),
                button=cast("str", self.drag_btn.currentData() or "left"),
            )
        if kind == "wait":
            return WaitAction(duration_s=self.wait_dur.value())
        if kind == "web_click":
            return WebClickAction(
                selector=self.wc_selector.text() or "body",
                button=cast("str", self.wc_button.currentData() or "left"),
                double=self.wc_double.isChecked(),
                force=self.wc_force.isChecked(),
            )
        if kind == "web_type":
            return WebTypeAction(
                selector=self.wt_selector.text() or "input",
                text=self.wt_text.text(),
                delay_ms=self.wt_delay.value(),
            )
        if kind == "web_navigate":
            return WebNavigateAction(
                url=self.wn_url.text() or "https://example.com",
                wait_until=cast("str", self.wn_wait.currentData() or "load"),
            )
        # extract_text
        return ExtractTextAction(
            region=Region(
                x=self.ext_x.value(), y=self.ext_y.value(),
                w=max(1, self.ext_w.value()), h=max(1, self.ext_h.value()),
            ),
            variable=self.ext_var.text() or "var",
            language=cast("str", self.ext_lang.currentData() or "kor+eng"),
            strip=self.ext_strip.isChecked(),
        )

    # --- region picker / template capture helpers ------------------------

    def set_region(self, x: int, y: int, w: int, h: int) -> None:
        self.trigger_type.setCurrentIndex(_TRIGGER_TYPES.index("image"))
        self.trigger_stack.setCurrentIndex(0)
        self.img_x.setValue(x); self.img_y.setValue(y)
        self.img_w.setValue(w); self.img_h.setValue(h)

    def set_template(self, rel_path: str) -> None:
        self.img_template.setText(rel_path)

    # --- web selector helpers --------------------------------------------

    _SELECTOR_FIELDS = ("we_selector", "wc_selector", "wt_selector")

    def set_web_selector(self, field_key: str, value: str) -> None:
        if field_key not in self._SELECTOR_FIELDS:
            return
        widget = getattr(self, field_key, None)
        if widget is None:
            return
        widget.setText(value)
        self._emit_changed()
