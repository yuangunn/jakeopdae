"""Modal sheet that asks 'what kind of step do you want to add?'.

Six tiles, one per step archetype. Returns the chosen kind via signal.
This is the keymacro-style ``[추가]`` UX from DESIGN.md.
"""

from __future__ import annotations

from typing import Literal, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import C


StepKind = Literal[
    "image_click", "time_wait", "pixel_wait", "key_press", "type_text", "pause",
    "web_element", "web_url_then_click", "web_navigate",
]


_TILES: list[tuple[StepKind, str, str, str]] = [
    ("image_click", "🖼", "이미지가 보이면", "화면 영역에서 등록한 이미지를 찾아 클릭/조작"),
    ("time_wait",   "⏱", "일정 시간 뒤에",     "지정한 시간만큼 기다렸다가 다음 동작"),
    ("pixel_wait",  "🎯", "특정 색이 보이면", "한 점의 RGB가 특정 값이 될 때까지 기다림"),
    ("key_press",   "⌨", "키 입력",             "단축키 / 키 조합 (예: ctrl+c)"),
    ("type_text",   "✏", "텍스트 입력",       "문자열을 키보드로 타이핑"),
    ("pause",       "⏸", "잠시 멈춤",          "다음 단계 전에 N초 멈추기"),
    ("web_element", "🌐", "웹: 요소가 보이면 클릭", "Chrome 페이지에서 셀렉터 매칭 + 클릭"),
    ("web_url_then_click", "🔗", "웹: URL 매칭 시 동작", "URL이 패턴과 일치할 때까지 대기"),
    ("web_navigate", "↗", "웹: URL로 이동", "Chrome 탭을 지정한 URL로 이동"),
    ("hybrid_image", "🌗", "이미지+URL (디버그 모드 X)", "일반 Chrome에서 이미지 매칭 + 주소창 URL 확인"),
    ("ocr_text", "🔤", "화면에서 텍스트가 보이면", "OCR로 영역 안의 글자를 읽어 매칭 (Tesseract 필요)"),
    ("extract_text", "📝", "텍스트 추출 → 변수", "OCR 결과를 ${var}에 저장. 다음 단계에서 ${var}로 참조"),
    ("schedule", "📅", "예약: 평일 9시 같은 시각에", "주중/주말, 매일, HH:MM 단위로 예약 실행"),
    ("clipboard", "📋", "클립보드 복사/붙여넣기", "Ctrl+C/V 또는 텍스트를 클립보드에 직접 쓰기"),
    ("http_request", "📡", "HTTP 요청 보내기", "GET/POST 등으로 외부 서버 호출 (웹훅, n8n, 자체 API)"),
    ("call_macro", "🔁", "다른 매크로 실행하기", "공통 로그인/사전 작업을 별도 yaml로 빼고 여기서 호출"),
]


class TypePicker(QDialog):
    chosen = Signal(str)  # one of StepKind

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("어떤 단계를 추가할까요?")
        self.setModal(True)
        self.setMinimumWidth(640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)

        title = QLabel("어떤 단계를 추가할까요?")
        title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', 'Pretendard Variable', sans-serif;"
            f"font-size: 22px; font-weight: 600; color: {C['on-surface']};"
            f"letter-spacing: -0.3px;"
        )
        outer.addWidget(title)

        sub = QLabel("아래에서 추가할 단계 종류를 골라주세요. 나중에 언제든 바꿀 수 있어요.")
        sub.setStyleSheet(f"color: {C['on-surface-variant']}; font-size: 13px;")
        outer.addWidget(sub)

        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (kind, icon, label, hint) in enumerate(_TILES):
            tile = self._make_tile(icon, label, hint)
            tile.clicked.connect(lambda _=False, k=kind: self._select(k))
            grid.addWidget(tile, i // 3, i % 3)
        outer.addLayout(grid)

        cancel_row = QVBoxLayout()
        cancel_row.setContentsMargins(0, 8, 0, 0)
        cancel = QPushButton("취소")
        cancel.setProperty("role", "ghost")
        cancel.clicked.connect(self.reject)
        cancel_row.addWidget(cancel, 0, Qt.AlignRight)
        outer.addLayout(cancel_row)

    def _make_tile(self, icon: str, label: str, hint: str) -> QPushButton:
        btn = QPushButton()
        btn.setProperty("role", "type-tile")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(120)

        text = (
            f"{icon}   {label}\n"
            f"\n"
            f"{hint}"
        )
        btn.setText(text)
        btn.setStyleSheet(
            f"""
            QPushButton[role="type-tile"] {{
                background-color: {C['surface-container-low']};
                color: {C['on-surface']};
                border: 1px solid {C['outline-variant']};
                border-radius: 14px;
                padding: 16px 18px;
                text-align: left;
                font-size: 13px;
                line-height: 1.6;
            }}
            QPushButton[role="type-tile"]:hover {{
                background-color: {C['surface-container-high']};
                border: 1px solid {C['primary']};
            }}
            """
        )
        return btn

    def _select(self, kind: str) -> None:
        self.chosen.emit(kind)
        self.accept()


def make_step_for_kind(kind: str, step_id: str):
    """Translate the picker's choice into a default Step instance."""
    from ..models import (
        CallMacroAction, ClickAction, ClipboardAction, ExtractTextAction,
        HttpAction, HybridImageTrigger, KeyAction, OcrTextTrigger,
        PixelColorTrigger, Region, ScheduleTrigger, Step, TimeTrigger,
        TypeAction, WaitAction, ImageTrigger, WebClickAction,
        WebElementVisibleTrigger, WebNavigateAction, WebUrlTrigger,
    )
    name_map = {
        "image_click": "이미지가 보이면 클릭",
        "time_wait": "시간 대기",
        "pixel_wait": "픽셀 색 대기",
        "key_press": "키 입력",
        "type_text": "텍스트 입력",
        "pause": "잠시 멈춤",
        "web_element": "웹 요소가 보이면 클릭",
        "web_url_then_click": "URL 매칭 대기",
        "web_navigate": "URL로 이동",
        "hybrid_image": "이미지+URL 매칭 시 클릭",
        "ocr_text": "텍스트가 보이면 동작",
        "extract_text": "텍스트 추출",
        "schedule": "예약 실행",
        "clipboard": "클립보드",
        "http_request": "HTTP 요청",
        "call_macro": "다른 매크로 호출",
    }
    if kind == "image_click":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=ImageTrigger(
                template="templates/.png",
                region=Region(x=100, y=100, w=400, h=300),
            ),
            action=ClickAction(relative_to_match=True, x=0, y=0),
        )
    if kind == "time_wait":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=1.0),
            action=WaitAction(duration_s=0.0),
        )
    if kind == "pixel_wait":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=PixelColorTrigger(x=0, y=0, rgb=(255, 255, 255)),
            action=WaitAction(duration_s=0.0),
        )
    if kind == "key_press":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=KeyAction(keys="enter"),
        )
    if kind == "type_text":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=TypeAction(text=""),
        )
    if kind == "pause":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=WaitAction(duration_s=0.5),
        )
    if kind == "web_element":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=WebElementVisibleTrigger(
                selector="button:has-text('다음')",
                timeout_s=10.0,
            ),
            action=WebClickAction(selector="button:has-text('다음')"),
        )
    if kind == "web_url_then_click":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=WebUrlTrigger(pattern="/lec/", mode="contains"),
            action=WaitAction(duration_s=0.0),
        )
    if kind == "web_navigate":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=WebNavigateAction(url="https://"),
        )
    if kind == "hybrid_image":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=HybridImageTrigger(
                template="templates/.png",
                region=Region(x=0, y=0, w=1920, h=1080),
                url_contains="example.com",
            ),
            action=ClickAction(relative_to_match=True, x=0, y=0),
        )
    if kind == "ocr_text":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=OcrTextTrigger(
                region=Region(x=200, y=200, w=600, h=200),
                text="다음",
                language="kor+eng",
            ),
            action=WaitAction(duration_s=0.0),
        )
    if kind == "extract_text":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=ExtractTextAction(
                region=Region(x=200, y=200, w=400, h=80),
                variable="otp",
                language="kor+eng",
            ),
        )
    if kind == "clipboard":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=ClipboardAction(op="paste"),
        )
    if kind == "http_request":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=HttpAction(
                url="https://example.com/webhook",
                method="POST",
                headers={"Content-Type": "application/json"},
                body='{"event":"macro_done"}',
            ),
        )
    if kind == "call_macro":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=CallMacroAction(path="shared/login.yaml"),
        )
    # schedule
    return Step(
        id=step_id, name=name_map[kind],
        trigger=ScheduleTrigger(at="09:00", weekdays=[0, 1, 2, 3, 4]),
        action=WaitAction(duration_s=0.0),
    )
