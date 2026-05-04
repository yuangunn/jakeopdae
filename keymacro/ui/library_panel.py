"""Slim collapsible left sidebar listing pinned / recent / folder macros.

Compact rows (~28px tall) with a 2px brass left border on the active
macro's row. Pinned items appear under a ★ section header at the top;
recent (last 8 non-pinned) appear under 최근; user-added folder roots
expand to list every ``*.yaml`` they contain.

Collapses to a 32px rail (toggle button + nothing else) so the sidebar
can be folded out of the way while keeping the global hotkey to bring
it back. Default: expanded if window is wider than ~1100px.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..storage.library import Library, LibraryEntry
from .theme import C


def _relative_time(ts: float) -> str:
    if ts <= 0:
        return ""
    d = max(0.0, time.time() - ts)
    if d < 60:
        return "방금"
    if d < 3600:
        return f"{int(d // 60)}분 전"
    if d < 86400:
        return f"{int(d // 3600)}시간 전"
    return f"{int(d // 86400)}일 전"


def _norm(p: str | Path) -> str:
    try:
        return str(Path(p).resolve())
    except Exception:
        return str(Path(p))


# ---------------------------------------------------------------------------


class LibraryRow(QPushButton):
    """One row in the library list. Looks like a list item, not a card."""

    pin_toggle_requested = Signal(str)
    remove_requested = Signal(str)
    reveal_requested = Signal(str)

    def __init__(
        self,
        path: str,
        name: str,
        meta: str,
        *,
        active: bool = False,
        pinned: bool = False,
    ) -> None:
        super().__init__()
        self._path = path
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(28)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        prefix = "★ " if pinned else "▸ "
        display = name or Path(path).stem
        meta_text = f"  · {meta}" if meta else ""
        self.setText(f"{prefix}{display}{meta_text}")
        self.setToolTip(path)
        self._apply_style(active, pinned)

    def _apply_style(self, active: bool, pinned: bool) -> None:
        edge = C["primary"] if active else "transparent"
        bg = C["surface-container-high"] if active else "transparent"
        text_color = C["primary"] if pinned else C["on-surface"]
        self.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                padding: 4px 8px 4px 10px;
                background-color: {bg};
                color: {text_color};
                border: none;
                border-left: 2px solid {edge};
                border-radius: 0;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {C['surface-container-high']};
            }}
            """
        )

    def path(self) -> str:
        return self._path

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        pin_act = menu.addAction("핀 토글")
        rm_act = menu.addAction("라이브러리에서 제거")
        menu.addSeparator()
        reveal_act = menu.addAction("탐색기에서 열기")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == pin_act:
            self.pin_toggle_requested.emit(self._path)
        elif chosen == rm_act:
            self.remove_requested.emit(self._path)
        elif chosen == reveal_act:
            self.reveal_requested.emit(self._path)


# ---------------------------------------------------------------------------


class LibraryPanel(QWidget):
    macro_picked = Signal(str)
    pin_toggle_requested = Signal(str)
    remove_requested = Signal(str)
    reveal_requested = Signal(str)
    folder_added = Signal(str)
    folder_removed = Signal(str)

    COLLAPSED_WIDTH = 32
    EXPANDED_WIDTH = 220

    def __init__(self, library: Library) -> None:
        super().__init__()
        self._library = library
        self._active_path: Optional[str] = None
        self._collapsed = False

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 8)
        outer.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(10, 0, 4, 0)
        header.setSpacing(2)

        self._title = QLabel("라이브러리")
        self._title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', 'Pretendard Variable', sans-serif;"
            f"font-size: 11px; font-weight: 700;"
            f"color: {C['on-surface-variant']}; letter-spacing: 0.6px;"
        )
        header.addWidget(self._title)
        header.addStretch()

        self._add_folder_btn = QPushButton("＋")
        self._add_folder_btn.setProperty("role", "icon-mini")
        self._add_folder_btn.setToolTip("폴더를 라이브러리에 추가")
        self._add_folder_btn.setFixedSize(20, 20)
        self._add_folder_btn.clicked.connect(self._on_add_folder)
        header.addWidget(self._add_folder_btn)

        self._toggle_btn = QPushButton("◀")
        self._toggle_btn.setProperty("role", "icon-mini")
        self._toggle_btn.setToolTip("사이드바 접기 (Ctrl+B)")
        self._toggle_btn.setFixedSize(20, 20)
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._toggle_btn)

        outer.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)
        self._inner_layout.addStretch()
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

        # Right-edge separator drawn via styling
        self.setMaximumWidth(self.EXPANDED_WIDTH)
        self.setMinimumWidth(self.EXPANDED_WIDTH)
        self.setStyleSheet(
            f"LibraryPanel {{"
            f"  background-color: {C['surface-container-low']};"
            f"  border-right: 1px solid {C['outline-variant']};"
            f"}}"
        )

    # --- public API -----------------------------------------------------

    def set_library(self, library: Library) -> None:
        self._library = library
        self.refresh()

    def set_active(self, path: Optional[str]) -> None:
        self._active_path = _norm(path) if path else None
        self.refresh()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.setMaximumWidth(self.COLLAPSED_WIDTH)
            self.setMinimumWidth(self.COLLAPSED_WIDTH)
            self._title.setVisible(False)
            self._add_folder_btn.setVisible(False)
            self._scroll.setVisible(False)
            self._toggle_btn.setText("▶")
            self._toggle_btn.setToolTip("사이드바 펴기 (Ctrl+B)")
        else:
            self.setMaximumWidth(self.EXPANDED_WIDTH)
            self.setMinimumWidth(self.EXPANDED_WIDTH)
            self._title.setVisible(True)
            self._add_folder_btn.setVisible(True)
            self._scroll.setVisible(True)
            self._toggle_btn.setText("◀")
            self._toggle_btn.setToolTip("사이드바 접기 (Ctrl+B)")

    # --- refresh content ------------------------------------------------

    def refresh(self) -> None:
        # Clear everything except the trailing stretch.
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        pinned = [e for e in self._library.entries if e.pinned]
        recent = sorted(
            (e for e in self._library.entries if not e.pinned),
            key=lambda e: e.last_opened_at,
            reverse=True,
        )

        if pinned:
            self._add_section("핀")
            for e in pinned:
                self._add_entry_row(e)

        if recent:
            self._add_section("최근")
            for e in recent[:8]:
                self._add_entry_row(e)

        for folder in self._library.folder_roots:
            self._add_folder_section(folder)

        if not pinned and not recent and not self._library.folder_roots:
            self._add_empty_hint()

    def _insert(self, widget: QWidget) -> None:
        # Insert before the trailing stretch.
        self._inner_layout.insertWidget(self._inner_layout.count() - 1, widget)

    def _add_section(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C['on-surface-variant']};"
            f"font-size: 9px; font-weight: 700; letter-spacing: 1px;"
            f"padding: 8px 10px 4px 10px;"
        )
        self._insert(lbl)

    def _add_entry_row(self, entry: LibraryEntry) -> None:
        active = (
            self._active_path is not None
            and _norm(entry.path) == self._active_path
        )
        row = LibraryRow(
            entry.path,
            name=entry.name,
            meta=_relative_time(entry.last_opened_at),
            active=active,
            pinned=entry.pinned,
        )
        row.clicked.connect(lambda _=False, p=entry.path: self.macro_picked.emit(p))
        row.pin_toggle_requested.connect(self.pin_toggle_requested)
        row.remove_requested.connect(self.remove_requested)
        row.reveal_requested.connect(self.reveal_requested)
        self._insert(row)

    def _add_folder_section(self, folder: str) -> None:
        folder_path = Path(folder)
        head = QHBoxLayout()
        head_wrap = QWidget()
        head_wrap.setLayout(head)
        head.setContentsMargins(10, 8, 6, 2)
        head.setSpacing(4)

        lbl = QLabel(f"📁 {folder_path.name}/")
        lbl.setToolTip(str(folder_path))
        lbl.setStyleSheet(
            f"color: {C['on-surface-variant']};"
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.4px;"
        )
        head.addWidget(lbl, 1)

        rm_btn = QPushButton("×")
        rm_btn.setProperty("role", "icon-mini")
        rm_btn.setFixedSize(18, 18)
        rm_btn.setToolTip("폴더를 라이브러리에서 제거")
        rm_btn.clicked.connect(
            lambda _=False, f=str(folder_path): self.folder_removed.emit(f)
        )
        head.addWidget(rm_btn)
        self._insert(head_wrap)

        if not folder_path.is_dir():
            warn = QLabel("(없음)")
            warn.setStyleSheet(
                f"color: {C['on-surface-variant']};"
                f"font-size: 10px; padding: 0 12px 4px 14px;"
            )
            self._insert(warn)
            return

        for yaml_file in sorted(folder_path.glob("*.yaml")):
            active = (
                self._active_path is not None
                and _norm(yaml_file) == self._active_path
            )
            row = LibraryRow(
                str(yaml_file),
                name=yaml_file.stem,
                meta="",
                active=active,
                pinned=False,
            )
            row.clicked.connect(
                lambda _=False, p=str(yaml_file): self.macro_picked.emit(p)
            )
            row.pin_toggle_requested.connect(self.pin_toggle_requested)
            row.remove_requested.connect(self.remove_requested)
            row.reveal_requested.connect(self.reveal_requested)
            self._insert(row)

    def _add_empty_hint(self) -> None:
        hint = QLabel(
            "아직 비어 있어요.\n파일을 열거나 [＋] 로\n폴더를 추가해 보세요."
        )
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {C['on-surface-variant']};"
            f"font-size: 10px; padding: 24px 12px;"
        )
        self._insert(hint)

    # --- handlers -------------------------------------------------------

    def _on_add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "라이브러리에 폴더 추가",
            str(Path.cwd()),
        )
        if d:
            self.folder_added.emit(d)
