"""Inline preview of what the runner saw when a step's trigger failed.

Wired to the ``failure_capture`` signal from :class:`QtRunObserver` so
the most recent failure image for each step is available without going
to disk. Click "📷 실패 화면" on an errored StepCard → this dialog pops
with the captured frame so the user can fix region / template /
selector without re-running.

Image flow:
    runner._save_failure_capture()      [worker thread]
        → observer.on_failure_capture(step_id, np.ndarray)
            → QtRunObserver.failure_capture signal             [GUI thread]
                → MainWindow._failure_captures[step_id] = ndarray
                → StepCard gets a "with_capture" hint on next set_error
                → user clicks → FailurePreviewDialog renders the ndarray

Why a custom dialog instead of just opening the PNG with the OS:
    - The ndarray is in BGR (OpenCV) — converting to QPixmap inline is
      cheaper than writing a temp PNG just to read it back.
    - We can overlay annotations later (the trigger's region rectangle,
      best-match score, etc.) without re-encoding.
    - Stays inside the dark theme — QFileDialog/Photos opens a foreign
      window each time.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import C


_MAX_PREVIEW_W = 720
_MAX_PREVIEW_H = 540


def _ndarray_to_qpixmap(image: np.ndarray) -> Optional[QPixmap]:
    """Convert an OpenCV BGR / BGRA / grayscale ndarray to QPixmap.

    Returns ``None`` if the array shape is unrecognised (e.g. the
    1×1×3 placeholder the runner emits when there's no real image).
    """
    if image is None or image.size == 0:
        return None
    arr = np.ascontiguousarray(image)
    h, w = arr.shape[:2]
    # Filter out the 1×1 placeholder ndarray emitted by the runner when
    # there's nothing real to show (e.g. web triggers without page).
    if h <= 1 and w <= 1:
        return None
    if arr.ndim == 2:
        qimg = QImage(arr.data, w, h, arr.strides[0], QImage.Format_Grayscale8)
    elif arr.ndim == 3 and arr.shape[2] == 3:
        # BGR → RGB swap. ``rgbSwapped`` does the conversion zero-copy
        # on Qt's side; cheaper than channel reshuffling in numpy.
        qimg = QImage(
            arr.data, w, h, arr.strides[0], QImage.Format_BGR888,
        ).rgbSwapped()
    elif arr.ndim == 3 and arr.shape[2] == 4:
        qimg = QImage(
            arr.data, w, h, arr.strides[0], QImage.Format_RGBA8888,
        )
    else:
        return None
    return QPixmap.fromImage(qimg.copy())  # copy so QImage doesn't alias data


class FailurePreviewDialog(QDialog):
    """Modeless dialog showing a single failure capture."""

    def __init__(
        self,
        step_id: str,
        image: np.ndarray,
        *,
        message: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"실패 화면 · {step_id}")
        self.setModal(False)
        self.setMinimumSize(320, 240)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 12)
        outer.setSpacing(10)

        header = QLabel(
            f"단계 <b>{step_id}</b> 가 트리거를 충족시키지 못했어요. "
            "아래는 마지막 시도에서 매크로가 본 화면입니다."
        )
        header.setWordWrap(True)
        header.setStyleSheet(
            f"color: {C['on-surface']}; font-size: 12px;"
        )
        outer.addWidget(header)

        if message:
            err = QLabel(f"오류: {message}")
            err.setWordWrap(True)
            err.setStyleSheet(
                f"color: {C['error']}; font-size: 11px;"
                f"font-family: 'JetBrains Mono', Consolas, monospace;"
            )
            outer.addWidget(err)

        pixmap = _ndarray_to_qpixmap(image)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(
            f"background-color: {C['surface-container-lowest']};"
            f"border: 1px solid {C['outline-variant']};"
            f"border-radius: 6px;"
        )
        if pixmap is None or pixmap.isNull():
            self._image_label.setText(
                "이 트리거는 화면 캡처를 만들지 않아요\n"
                "(예: 시간 트리거, 웹 페이지가 아직 안 떠 있는 경우)."
            )
            self._image_label.setMinimumHeight(140)
        else:
            scaled = pixmap.scaled(
                _MAX_PREVIEW_W, _MAX_PREVIEW_H,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            self._image_label.setPixmap(scaled)
        outer.addWidget(self._image_label, 1)

        # Footer row — close button on the right.
        footer = QHBoxLayout()
        footer.addStretch()
        close = QPushButton("닫기")
        close.setProperty("role", "ghost")
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.close)
        footer.addWidget(close)
        outer.addLayout(footer)
