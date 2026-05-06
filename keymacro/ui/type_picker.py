"""Modal sheet that asks 'what kind of step do you want to add?'.

Compact 2-column grid grouped by category, wrapped in a scroll area
so the sheet stays roughly 700×560 even as new step kinds get added.
Filter box at the top lets the user type-search by Korean keywords.
"""

from __future__ import annotations

from typing import Literal, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .theme import C


StepKind = Literal[
    "image_click", "time_wait", "pixel_wait", "key_press", "type_text", "pause",
    "web_element", "web_url_then_click", "web_navigate",
]


# Step kinds grouped by user mental model: when do you reach for them?
#  - 화면/타이밍: 시각·시간 기반 트리거 (뭔가 보이거나 시간이 되면)
#  - 입력/매크로: 키보드/마우스 직접 조작 + 흐름 제어
#  - 웹 (Chrome): 브라우저 자동화
#  - 외부 연동: 데이터를 매크로 밖으로 보내거나 받기
# Each tuple: ``(group title, [(kind, icon, label, hint), ...])``.
_GROUPS: list[tuple[str, list[tuple[StepKind, str, str, str]]]] = [
    ("화면 / 타이밍", [
        ("image_click", "🖼", "이미지가 보이면", "화면 영역에서 등록한 이미지를 찾아 클릭/조작"),
        ("ocr_text", "🔤", "화면 텍스트가 보이면", "OCR로 영역 글자를 읽어 매칭 (Tesseract 필요)"),
        ("pixel_wait", "🎯", "특정 색이 보이면", "한 점의 RGB가 특정 값이 될 때까지 대기"),
        ("time_wait", "⏱", "일정 시간 뒤에", "지정한 시간만큼 기다렸다가 다음 동작"),
        ("schedule", "📅", "예약 시각이 되면", "평일/주말/매일 HH:MM 단위 예약 실행"),
        ("clipboard_otp", "📋✨", "클립보드에 OTP가 오면", "본인인증 6자리 등 정규식 매칭 대기"),
    ]),
    ("입력 / 흐름", [
        ("key_press", "⌨", "키 입력", "단축키 / 키 조합 (예: ctrl+c)"),
        ("type_text", "✏", "텍스트 입력", "문자열을 키보드로 타이핑 (한글 자동 paste)"),
        ("pause", "⏸", "잠시 멈춤", "다음 단계 전에 N초 멈추기"),
        ("clipboard", "📋", "클립보드 복사/붙여넣기", "Ctrl+C/V 또는 텍스트를 클립보드에 직접 쓰기"),
        ("extract_text", "📝", "텍스트 추출 → 변수", "OCR 결과를 ${var}에 저장"),
        ("call_macro", "🔁", "다른 매크로 실행", "공통 로그인 등을 별도 yaml로 빼고 호출"),
    ]),
    ("웹 (Chrome)", [
        ("web_element", "🌐", "웹: 요소 보이면 클릭", "Chrome 페이지 셀렉터 매칭 + 클릭"),
        ("web_url_then_click", "🔗", "웹: URL 매칭 대기", "URL이 패턴과 일치할 때까지 대기"),
        ("web_navigate", "↗", "웹: URL로 이동", "Chrome 탭을 지정한 URL로 이동"),
        ("hybrid_image", "🌗", "이미지 + URL (일반 Chrome)", "디버그 모드 없이 이미지 매칭 + 주소창 URL 확인"),
    ]),
    ("외부 연동 / 시스템", [
        ("http_request", "📡", "HTTP 요청 보내기", "GET/POST 등으로 웹훅·API 호출"),
        ("notify", "🔔", "외부로 알림 보내기", "Telegram / Slack / Discord / KakaoWork"),
        ("window_resize", "🪟", "창 크기/위치 조정", "Chrome·메모장 등 창 크기·위치 변경 (Windows)"),
    ]),
]


class TypePicker(QDialog):
    chosen = Signal(str)  # one of StepKind

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("어떤 단계를 추가할까요?")
        self.setModal(True)
        # Compact size — all kinds are reachable via scroll, so the
        # dialog doesn't have to be huge to show every option at once.
        self.resize(680, 560)
        self.setMinimumSize(560, 420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(10)

        # --- header: title + filter -----------------------------------
        title = QLabel("어떤 단계를 추가할까요?")
        title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', sans-serif;"
            f"font-size: 18px; font-weight: 600; color: {C['on-surface']};"
            f"letter-spacing: -0.2px;"
        )
        outer.addWidget(title)

        sub = QLabel(
            "키워드로 검색하거나 아래 카테고리에서 골라 주세요. 나중에 언제든 바꿀 수 있어요."
        )
        sub.setStyleSheet(f"color: {C['on-surface-variant']}; font-size: 11px;")
        outer.addWidget(sub)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText(
            "🔍 검색 (예: '클립보드', 'OTP', 'Chrome', '예약', '알림')"
        )
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)
        outer.addWidget(self._filter)

        # --- scroll area --------------------------------------------
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)

        body = QWidget()
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(0, 0, 4, 0)  # 4 px right for scrollbar
        body_l.setSpacing(14)

        # Keep references to (tile_button, kind, group_header_widget,
        # haystack_text) so we can hide/show during search filtering.
        self._tiles: list[tuple[QPushButton, str, str]] = []
        self._group_headers: list[QLabel] = []
        self._group_grids: list[QWidget] = []

        for group_title, items in _GROUPS:
            header = QLabel(group_title)
            header.setStyleSheet(
                f"color: {C['on-surface-variant']};"
                f"font-size: 10px; font-weight: 700;"
                f"letter-spacing: 1px; padding: 4px 0 2px 2px;"
            )
            self._group_headers.append(header)
            body_l.addWidget(header)

            grid_wrap = QWidget()
            grid = QGridLayout(grid_wrap)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(8)
            for i, (kind, icon, label, hint) in enumerate(items):
                tile = self._make_tile(icon, label, hint)
                tile.clicked.connect(lambda _=False, k=kind: self._select(k))
                grid.addWidget(tile, i // 2, i % 2)
                # Haystack: kind + label + hint, lower-cased so we can
                # match Korean substrings cheaply.
                haystack = f"{kind} {label} {hint}".casefold()
                self._tiles.append((tile, haystack, group_title))
            self._group_grids.append(grid_wrap)
            body_l.addWidget(grid_wrap)

        body_l.addStretch()
        self._scroll.setWidget(body)
        outer.addWidget(self._scroll, 1)

        # --- footer ---------------------------------------------------
        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("취소")
        cancel.setProperty("role", "ghost")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        outer.addLayout(footer)

        # Focus the filter so keyboard-first users can start typing
        # immediately when the dialog opens.
        self._filter.setFocus()

    def _make_tile(self, icon: str, label: str, hint: str) -> QPushButton:
        """Compact tile — single line of label + small hint, ~76 px tall.

        About a third the height of the previous tile so the full
        catalogue fits a 560-tall dialog with breathing room."""
        btn = QPushButton()
        btn.setProperty("role", "type-tile")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(64)

        # Icon first row, label inline; hint on a second line in muted
        # colour. Plain-text widget so no rich-text overhead.
        btn.setText(f"{icon}   {label}\n{hint}")
        btn.setStyleSheet(
            f"""
            QPushButton[role="type-tile"] {{
                background-color: {C['surface-container-low']};
                color: {C['on-surface']};
                border: 1px solid {C['outline-variant']};
                border-radius: 10px;
                padding: 10px 12px;
                text-align: left;
                font-size: 12px;
            }}
            QPushButton[role="type-tile"]:hover {{
                background-color: {C['surface-container-high']};
                border: 1px solid {C['primary']};
            }}
            """
        )
        return btn

    def _apply_filter(self, text: str) -> None:
        """Hide tiles whose haystack doesn't contain the query, then
        hide a group header entirely if all of its tiles are hidden."""
        needle = text.casefold().strip()
        # Per-group visibility tally; used to hide empty headers.
        group_visible: dict[str, bool] = {g: False for g, _ in _GROUPS}

        for tile, haystack, group in self._tiles:
            visible = needle in haystack if needle else True
            tile.setVisible(visible)
            if visible:
                group_visible[group] = True

        for header, (group_title, _) in zip(self._group_headers, _GROUPS):
            header.setVisible(group_visible[group_title])
        for grid_wrap, (group_title, _) in zip(self._group_grids, _GROUPS):
            grid_wrap.setVisible(group_visible[group_title])

    def _select(self, kind: str) -> None:
        self.chosen.emit(kind)
        self.accept()


def make_step_for_kind(kind: str, step_id: str):
    """Translate the picker's choice into a default Step instance."""
    from ..models import (
        CallMacroAction, ClickAction, ClipboardAction,
        ClipboardChangeTrigger, ExtractTextAction, HttpAction,
        HybridImageTrigger, KeyAction, NotifyAction, OcrTextTrigger,
        PixelColorTrigger, Region, ScheduleTrigger, Step, TimeTrigger,
        TypeAction, WaitAction, ImageTrigger, WebClickAction,
        WebElementVisibleTrigger, WebNavigateAction, WebUrlTrigger,
        WindowResizeAction,
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
        "clipboard_otp": "클립보드 OTP 대기",
        "notify": "외부 알림",
        "window_resize": "창 크기 조정",
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
    if kind == "clipboard_otp":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=ClipboardChangeTrigger(
                pattern=r"\d{6}",
                capture_var="otp",
                timeout_s=120.0,
            ),
            # Default to typing the captured OTP — the most common
            # follow-up action.
            action=TypeAction(text="${otp}"),
        )
    if kind == "notify":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=NotifyAction(
                provider="telegram",
                text="작업대 매크로 완료",
            ),
        )
    if kind == "window_resize":
        return Step(
            id=step_id, name=name_map[kind],
            trigger=TimeTrigger(delay_s=0.0),
            action=WindowResizeAction(
                title_match="Chrome",
                mode="fullscreen_monitor",
                monitor_index=0,
            ),
        )
    # schedule
    return Step(
        id=step_id, name=name_map[kind],
        trigger=ScheduleTrigger(at="09:00", weekdays=[0, 1, 2, 3, 4]),
        action=WaitAction(duration_s=0.0),
    )
