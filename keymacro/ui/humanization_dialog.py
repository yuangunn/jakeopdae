"""Modal dialog for editing the macro's humanization (anti-bot) knobs.

Opened from the ⋮ overflow menu. Shows the three jitter
percentages / pixel offset, with hint labels explaining the typical
range so users don't have to guess.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..models import HumanizationConfig
from .theme import C


class HumanizationDialog(QDialog):
    """Modal editor for :class:`HumanizationConfig`. ``saved`` fires
    with the new config; cancel emits nothing."""

    saved = Signal(HumanizationConfig)

    def __init__(
        self,
        config: HumanizationConfig,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("매크로 방지 설정")
        self.setModal(True)
        self.resize(440, 360)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        title = QLabel("🛡  매크로 방지 (anti-bot detection)")
        title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', sans-serif;"
            f"font-size: 16px; font-weight: 600; color: {C['on-surface']};"
        )
        outer.addWidget(title)

        intro = QLabel(
            "사이트가 봇으로 의심하는 정형화된 입력 패턴을 살짝 흩뿌려요.\n"
            "0이면 기존처럼 정확한 시간 / 픽셀로 동작."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color: {C['on-surface-variant']}; font-size: 12px;"
        )
        outer.addWidget(intro)

        f = QFormLayout()
        f.setSpacing(10)

        self.time_jitter = QDoubleSpinBox()
        self.time_jitter.setRange(0.0, 100.0)
        self.time_jitter.setSingleStep(1.0)
        self.time_jitter.setSuffix(" %")
        self.time_jitter.setValue(config.time_jitter_pct)
        self.time_jitter.setToolTip(
            "대기 / 폴링 시간에 ±이 % 만큼 랜덤. 5~15 정도가 자연스러움.",
        )

        self.click_px = QSpinBox()
        self.click_px.setRange(0, 50)
        self.click_px.setSingleStep(1)
        self.click_px.setSuffix(" px")
        self.click_px.setValue(config.click_position_px)
        self.click_px.setToolTip(
            "클릭 좌표에 ±이 px 만큼 랜덤 오차. 1~3 px이 적당.",
        )

        self.type_jitter = QDoubleSpinBox()
        self.type_jitter.setRange(0.0, 100.0)
        self.type_jitter.setSingleStep(1.0)
        self.type_jitter.setSuffix(" %")
        self.type_jitter.setValue(config.type_interval_jitter_pct)
        self.type_jitter.setToolTip(
            "타이핑 글자 사이 간격에 ±이 % 만큼 랜덤. 사람은 보통 ±20~40%.",
        )

        f.addRow("시간 지연 흔들림", self.time_jitter)
        f.addRow("클릭 좌표 오차", self.click_px)
        f.addRow("타이핑 간격 흔들림", self.type_jitter)

        outer.addLayout(f)
        outer.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("취소")
        cancel.setProperty("role", "ghost")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("적용")
        ok.setProperty("role", "primary")
        ok.clicked.connect(self._on_save)
        footer.addWidget(cancel)
        footer.addWidget(ok)
        outer.addLayout(footer)

    def _on_save(self) -> None:
        cfg = HumanizationConfig(
            time_jitter_pct=self.time_jitter.value(),
            click_position_px=self.click_px.value(),
            type_interval_jitter_pct=self.type_jitter.value(),
        )
        self.saved.emit(cfg)
        self.accept()
