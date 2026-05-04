"""Main window — compact 작업대 layout.

Default 1080x680 fits 720p at 100% scale and stays usable up to 200% DPI.
Tiers (top to bottom): header (compact) → toolbar → splitter (list / form
in scroll area) → sticky 64px transport bar.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.chrome_launcher import (
    ensure_chrome_running,
    is_cdp_listening,
    DEFAULT_CDP_PORT,
)
from ..core.control import RunControl
from ..core.observer import MultiObserver
from ..core.recorder import events_to_macro
from ..history import HistoryStore, default_history_path
from ..hotkey.manager import HotkeyManager
from ..models import (
    ClickAction,
    Macro,
    Step,
    TimeTrigger,
    ImageTrigger,
    PixelColorTrigger,
)
from ..models.web import WebSessionConfig
from ..storage.library import load_library, save_library
from ..storage.yaml_repo import load_macro, save_macro
from ..storage.zip_archive import export_macro, import_macro
from .empty_state import EmptyState  # noqa: F401
from .library_panel import LibraryPanel
from .observer_bridge import QtRunObserver
from .picker_thread import PickerThread
from .recorder_controller import RecorderController
from .region_picker import RegionPickerOverlay
from .runner_thread import RunnerThread
from .step_form import StepForm
from .step_list_panel import StepListPanel
from .template_capture import capture_template
from .theme import C, apply_theme
from .transport_bar import TransportBar
from .tray import TrayIcon
from .type_picker import TypePicker, make_step_for_kind

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------


class _StatusPill(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setProperty("role", "status-pill")
        self.setProperty("state", "idle")
        h = QHBoxLayout(self)
        h.setContentsMargins(9, 3, 11, 3)
        h.setSpacing(6)

        self._dot = QFrame()
        self._dot.setFixedSize(7, 7)
        self._dot.setStyleSheet(
            f"background-color: {C['outline-variant']}; border-radius: 3px;"
        )
        h.addWidget(self._dot)

        self._lbl = QLabel("대기 중")
        self._lbl.setStyleSheet(
            f"color: {C['on-surface']}; font-size: 11px; font-weight: 600;"
            f"letter-spacing: 0.4px;"
        )
        h.addWidget(self._lbl)

    def set_state(self, state: str, label: str) -> None:
        self.setProperty("state", state)
        self._lbl.setText(label)
        if state == "running":
            self._dot.setStyleSheet("background-color: #D44A30; border-radius: 3px;")
        elif state == "paused":
            self._dot.setStyleSheet(
                f"background-color: {C['secondary']}; border-radius: 3px;"
            )
        else:
            self._dot.setStyleSheet(
                f"background-color: {C['outline-variant']}; border-radius: 3px;"
            )
        self.style().unpolish(self)
        self.style().polish(self)


# ---------------------------------------------------------------------------


def _trigger_kind_of(step: Step) -> str:
    if isinstance(step.trigger, ImageTrigger):
        return "image"
    if isinstance(step.trigger, TimeTrigger):
        return "time"
    if isinstance(step.trigger, PixelColorTrigger):
        return "pixel"
    return "image"


# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self, *, debug_capture_dir: Optional[Path] = None) -> None:
        super().__init__()
        self.setWindowTitle("작업대 · keymacro")
        self.resize(1280, 700)

        self._macro: Macro = _empty_macro()
        self._macro_path: Optional[Path] = None
        self._dirty: bool = False
        self._debug_capture_dir = debug_capture_dir

        self._control = RunControl()
        self._observer = QtRunObserver()
        self._runner_thread: Optional[RunnerThread] = None

        self._library = load_library()
        # Auto-seed the library with the bundled examples folder so a
        # brand-new install doesn't open to an empty sidebar.
        self._seed_examples_on_first_launch()
        self._picker_thread: Optional[PickerThread] = None
        self._picker_field: Optional[str] = None

        # Memento stack for Ctrl+Z. Snapshots are macro JSON dumps; the
        # stack is bounded so an editing marathon doesn't grow without
        # bound. Text edits in the form are *not* snapshotted (too
        # granular) — only structural ops (add/remove/move/duplicate).
        self._undo_stack: list[dict] = []
        self._undo_max = 50

        # Persistent run history — every Runner invocation is mirrored.
        self._history = HistoryStore(default_history_path())

        # Recorder lives outside the runner stack — it can be on any time.
        self._recorder_ctrl = RecorderController(self)
        self._recorder_ctrl.stopped_externally.connect(
            self._on_recording_stopped_via_hotkey,
        )

        apply_theme(self)
        self._build_ui()
        self._wire_signals()
        self._setup_hotkeys()
        self._setup_tray()
        self._reload_step_list()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        # Center on whichever screen the cursor is on right now.
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            fg = self.frameGeometry()
            fg.moveCenter(geo.center())
            self.move(fg.topLeft())

    # --- UI assembly ----------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(8)

        outer.addLayout(self._build_header())

        rule = QFrame()
        rule.setFrameShape(QFrame.HLine)
        rule.setStyleSheet(f"color: {C['outline-variant']};")
        rule.setFixedHeight(1)
        outer.addWidget(rule)

        outer.addLayout(self._build_toolbar())

        # Body splitter — 3 panes: library / step list / form
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        self.library_panel = LibraryPanel(self._library)
        splitter.addWidget(self.library_panel)

        self.list_panel = StepListPanel()
        splitter.addWidget(self.list_panel)

        # Right side: scrollable form
        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setFrameShape(QFrame.NoFrame)
        self.form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.form = StepForm()
        self.form_scroll.setWidget(self.form)
        splitter.addWidget(self.form_scroll)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 6)
        splitter.setSizes([220, 440, 600])
        outer.addWidget(splitter, 1)

        self.transport = TransportBar()
        outer.addWidget(self.transport)

        self.setCentralWidget(central)

        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        title = QLabel("작업대")
        title.setStyleSheet(
            f"font-family: 'Space Grotesk', 'Noto Sans KR', 'Pretendard Variable', sans-serif;"
            f"font-size: 20px; font-weight: 600; color: {C['on-surface']};"
            f"letter-spacing: -0.4px;"
        )
        row.addWidget(title)

        self._sub_lbl = QLabel("(저장 안 됨)")
        self._sub_lbl.setStyleSheet(
            f"color: {C['on-surface-variant']};"
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
            f"font-size: 10px; padding-bottom: 2px;"
        )
        row.addWidget(self._sub_lbl)
        row.addStretch()

        self.status_pill = _StatusPill()
        row.addWidget(self.status_pill)
        return row

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

        def gh(label: str, tip: str = "") -> QPushButton:
            b = QPushButton(label)
            b.setProperty("role", "ghost")
            b.setCursor(Qt.PointingHandCursor)
            if tip:
                b.setToolTip(tip)
            return b

        self.btn_new = gh("새로", "새 매크로 (Ctrl+N)")
        self.btn_open = gh("열기", "매크로 열기 (Ctrl+O)")
        self.btn_save = gh("저장", "저장 (Ctrl+S)")
        self.btn_save_as = gh("다른 이름", "다른 이름으로 저장")
        self.btn_export = gh(".kma 내보내기", "매크로 + 템플릿을 단일 파일로")
        self.btn_import = gh(".kma 가져오기", ".kma 묶음 풀어 불러오기")
        for b in (
            self.btn_new, self.btn_open, self.btn_save, self.btn_save_as,
            self.btn_export, self.btn_import,
        ):
            row.addWidget(b)
        row.addStretch()

        # Chrome status pill — sage when CDP port 9222 is listening.
        self.btn_chrome = QPushButton("○  Chrome 시작")
        self.btn_chrome.setProperty("role", "ghost")
        self.btn_chrome.setProperty("state", "idle")
        self.btn_chrome.setMinimumWidth(140)
        self.btn_chrome.setCursor(Qt.PointingHandCursor)
        self.btn_chrome.setToolTip(
            "디버그 모드 Chrome 띄우기 — 웹 매크로 / 요소 picker가 여기에 연결됨"
        )
        self.btn_chrome.clicked.connect(self._on_chrome_launch_clicked)
        row.addWidget(self.btn_chrome)

        # Recorder + history buttons — sit alongside the Chrome status pill.
        self.btn_record = QPushButton("●  녹화")
        self.btn_record.setProperty("role", "ghost")
        self.btn_record.setMinimumWidth(110)
        self.btn_record.setCursor(Qt.PointingHandCursor)
        self.btn_record.setToolTip(
            "마우스 / 키보드 입력을 기록해 매크로 자동 생성. F8로 정지",
        )
        self.btn_record.clicked.connect(self._on_record_toggle)
        row.addWidget(self.btn_record)

        self.btn_history = QPushButton("이력")
        self.btn_history.setProperty("role", "ghost")
        self.btn_history.setCursor(Qt.PointingHandCursor)
        self.btn_history.setToolTip("최근 매크로 실행 기록 보기")
        self.btn_history.clicked.connect(self._on_show_history)
        row.addWidget(self.btn_history)

        # Refresh status every 4 seconds (port liveness probe is cheap).
        from PySide6.QtCore import QTimer
        self._chrome_status_timer = QTimer(self)
        self._chrome_status_timer.setInterval(4000)
        self._chrome_status_timer.timeout.connect(self._refresh_chrome_status)
        self._chrome_status_timer.start()
        self._refresh_chrome_status()
        return row

    def _refresh_chrome_status(self) -> None:
        listening = is_cdp_listening(timeout_s=0.15)
        if listening:
            # Sage-coloured dot prefix so the active state pops out without
            # fighting the global ghost-pill style.
            self.btn_chrome.setText("●  Chrome 연결됨")
            self.btn_chrome.setProperty("state", "listening")
        else:
            self.btn_chrome.setText("○  Chrome 시작")
            self.btn_chrome.setProperty("state", "idle")
        self.btn_chrome.style().unpolish(self.btn_chrome)
        self.btn_chrome.style().polish(self.btn_chrome)

    def _on_chrome_launch_clicked(self) -> None:
        ok, msg = ensure_chrome_running()
        if ok:
            self.statusBar().showMessage(msg, 6000)
        else:
            QMessageBox.warning(self, "Chrome 시작 실패", msg)
        self._refresh_chrome_status()

    def _wire_signals(self) -> None:
        self.btn_new.clicked.connect(self._on_new)
        self.btn_open.clicked.connect(self._on_open)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save_as.clicked.connect(self._on_save_as)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_import.clicked.connect(self._on_import)

        self.list_panel.add_requested.connect(self._on_add_step)
        self.list_panel.selected.connect(self._on_step_selected)
        self.list_panel.delete_requested.connect(self._on_remove_step)
        self.list_panel.duplicate_requested.connect(self._on_duplicate_step)
        self.list_panel.move_up_requested.connect(lambda r: self._move_step(-1))
        self.list_panel.move_down_requested.connect(lambda r: self._move_step(+1))
        self.list_panel.reorder_requested.connect(self._on_reorder_steps)
        self.list_panel.examples_requested.connect(self._on_browse_examples)

        self.form.step_changed.connect(self._on_form_changed)
        self.form.pick_region_requested.connect(self._pick_region)
        self.form.capture_template_requested.connect(self._capture_template)
        self.form.pick_web_selector_requested.connect(self._on_pick_web_selector)

        self.transport.start_requested.connect(self._on_start)
        self.transport.stop_requested.connect(self._on_stop)
        self.transport.pause_requested.connect(self._on_pause)

        self._observer.run_started.connect(
            lambda n: self.status_pill.set_state("running", f"실행 중 · {n}")
        )
        self._observer.match_attempt.connect(self.transport.set_match)
        self._observer.step_started.connect(self._on_step_started)
        self._observer.step_ended.connect(self._on_step_ended)
        self._observer.run_ended.connect(self._on_run_ended)

        QShortcut(QKeySequence.Save, self, activated=self._on_save)
        QShortcut(QKeySequence.New, self, activated=self._on_new)
        QShortcut(QKeySequence.Open, self, activated=self._on_open)
        QShortcut(
            QKeySequence("Ctrl+B"), self,
            activated=self.library_panel.toggle_collapsed,
        )
        # Ctrl+D — duplicate the currently-selected step.
        QShortcut(
            QKeySequence("Ctrl+D"), self,
            activated=self._duplicate_selected_step,
        )
        # Ctrl+Z — undo the last structural change.
        QShortcut(
            QKeySequence.Undo, self,
            activated=self._undo,
        )

        # Library panel signals
        self.library_panel.macro_picked.connect(self._on_library_picked)
        self.library_panel.pin_toggle_requested.connect(self._on_library_pin_toggle)
        self.library_panel.remove_requested.connect(self._on_library_remove)
        self.library_panel.reveal_requested.connect(self._on_library_reveal)
        self.library_panel.folder_added.connect(self._on_library_folder_added)
        self.library_panel.folder_removed.connect(self._on_library_folder_removed)

    def _setup_hotkeys(self) -> None:
        self._hotkeys = HotkeyManager(
            on_start=lambda: self.transport.start_requested.emit(),
            on_stop=lambda: self.transport.stop_requested.emit(),
            on_pause=lambda: self.transport.pause_requested.emit(),
        )
        try:
            self._hotkeys.start()
        except Exception:
            log.exception("hotkey listener could not start")

    def _setup_tray(self) -> None:
        self._tray = TrayIcon(self)
        self._tray.show_requested.connect(self.showNormal)
        self._tray.start_requested.connect(self._on_start)
        self._tray.stop_requested.connect(self._on_stop)
        self._tray.quit_requested.connect(self.close)
        self._tray.show()

    # --- step list management -------------------------------------------

    def _refresh_transport_kind_lookup(self) -> None:
        self.transport.set_step_kind_lookup(
            {s.id: _trigger_kind_of(s) for s in self._macro.steps}
        )

    def _bundled_examples_dir(self) -> Optional[Path]:
        """Locate the ``examples/`` directory shipped alongside the package.

        For PyInstaller one-file bundles, ``sys._MEIPASS`` points at the
        per-launch extraction; for dev installs it sits at the repo root
        next to the ``keymacro/`` package.
        """
        import sys
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = Path(meipass) / "examples"
            if p.is_dir():
                return p
        candidate = Path(__file__).resolve().parents[2] / "examples"
        return candidate if candidate.is_dir() else None

    def _seed_examples_on_first_launch(self) -> bool:
        """First-time install — register bundled examples in the
        library so the sidebar isn't empty."""
        if self._library.entries or self._library.folder_roots:
            return False
        examples = self._bundled_examples_dir()
        if examples is None:
            return False
        self._library.add_folder(examples)
        save_library(self._library)
        log.info("first launch — seeded examples folder %s", examples)
        return True

    def _reload_step_list(self, select_index: int = 0) -> None:
        examples_available = self._bundled_examples_dir() is not None
        self.list_panel.set_steps(
            list(self._macro.steps),
            select_index=select_index,
            show_examples_button=(not self._macro.steps) and examples_available,
        )
        self._refresh_transport_kind_lookup()
        if self._macro.steps:
            self.form_scroll.setVisible(True)
            self.form.load_step(self._macro.steps[
                self.list_panel.selected_row() if self.list_panel.selected_row() >= 0
                else 0
            ])
        else:
            self.form_scroll.setVisible(False)
        self._update_title()

    def _on_browse_examples(self) -> None:
        """Open a File-Open dialog rooted in the bundled examples
        folder so first-time users see what a real macro looks like."""
        examples = self._bundled_examples_dir()
        if examples is None:
            return
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "예제 매크로 살펴보기", str(examples),
            "매크로 YAML (*.yaml *.yml)",
        )
        if not path:
            return
        self._load_macro_from_path(Path(path))

    def _on_step_selected(self, row: int) -> None:
        self.list_panel.set_selected(row)
        if 0 <= row < len(self._macro.steps):
            self.form_scroll.setVisible(True)
            self.form.load_step(self._macro.steps[row])

    def _on_form_changed(self) -> None:
        idx = self.list_panel.selected_row()
        if idx < 0 or idx >= len(self._macro.steps):
            return
        try:
            new_step = self.form.to_step()
        except Exception:
            return
        if new_step != self._macro.steps[idx]:
            self._macro.steps[idx] = new_step
            self._dirty = True
            self.list_panel.update_step(idx, new_step)
            self._refresh_transport_kind_lookup()
            self._update_title()

    # --- undo plumbing --------------------------------------------------

    def _snapshot_macro(self) -> None:
        """Push the current macro state onto the undo stack.

        Called *before* every structural change. Form-level text edits
        skip this — too granular and the user wouldn't expect each
        keystroke to be its own undo point.
        """
        try:
            snap = self._macro.model_dump(mode="json")
        except Exception:
            return
        self._undo_stack.append(snap)
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)

    def _undo(self) -> None:
        if not self._undo_stack:
            self.statusBar().showMessage("되돌릴 변경 없음", 2500)
            return
        snap = self._undo_stack.pop()
        try:
            self._macro = Macro.model_validate(snap)
        except Exception:
            self.statusBar().showMessage("되돌리기 실패", 3000)
            return
        self._dirty = True
        self._reload_step_list(select_index=0)
        self.statusBar().showMessage(
            f"되돌렸어요  · 남은 undo {len(self._undo_stack)}건", 2500,
        )

    def _duplicate_selected_step(self) -> None:
        row = self.list_panel.selected_row()
        if row >= 0:
            self._on_duplicate_step(row)

    # --- step list edits ------------------------------------------------

    def _on_add_step(self) -> None:
        picker = TypePicker(self)
        picker.chosen.connect(self._on_kind_picked)
        picker.exec()

    def _on_kind_picked(self, kind: str) -> None:
        existing = {s.id for s in self._macro.steps}
        i = len(self._macro.steps)
        sid = f"step{i + 1}"
        while sid in existing:
            i += 1
            sid = f"step{i + 1}"
        new_step = make_step_for_kind(kind, sid)
        self._snapshot_macro()
        self._macro.steps.append(new_step)
        self._dirty = True
        self._reload_step_list(select_index=len(self._macro.steps) - 1)

    def _on_remove_step(self, row: int) -> None:
        if not (0 <= row < len(self._macro.steps)):
            return
        ans = QMessageBox.question(
            self, "단계 삭제",
            f"단계 '{self._macro.steps[row].name or self._macro.steps[row].id}' 을(를) 삭제할까요?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        self._snapshot_macro()
        self._macro.steps.pop(row)
        self._dirty = True
        self._reload_step_list(select_index=max(0, row - 1))

    def _on_duplicate_step(self, row: int) -> None:
        if not (0 <= row < len(self._macro.steps)):
            return
        original = self._macro.steps[row]
        existing = {s.id for s in self._macro.steps}
        new_id = f"{original.id}_copy"
        i = 2
        while new_id in existing:
            new_id = f"{original.id}_copy{i}"
            i += 1
        copy = original.model_copy(update={"id": new_id})
        self._snapshot_macro()
        self._macro.steps.insert(row + 1, copy)
        self._dirty = True
        self._reload_step_list(select_index=row + 1)

    def _move_step(self, delta: int) -> None:
        idx = self.list_panel.selected_row()
        new = idx + delta
        if idx < 0 or new < 0 or new >= len(self._macro.steps):
            return
        self._snapshot_macro()
        self._macro.steps[idx], self._macro.steps[new] = (
            self._macro.steps[new], self._macro.steps[idx],
        )
        self._dirty = True
        self._reload_step_list(select_index=new)

    def _on_reorder_steps(self, src: int, target: int) -> None:
        """Drag-drop reorder. ``target`` is the insertion index in the
        original list (before pop). After popping ``src`` we need to
        decrement ``target`` by one if it was past the source position,
        otherwise the destination shifts left by one slot."""
        n = len(self._macro.steps)
        if not (0 <= src < n) or not (0 <= target <= n):
            return
        if src < target:
            target -= 1
        if src == target:
            return
        self._snapshot_macro()
        step = self._macro.steps.pop(src)
        self._macro.steps.insert(target, step)
        self._dirty = True
        self._reload_step_list(select_index=target)

    # --- file ops -------------------------------------------------------

    def _update_title(self) -> None:
        if self._macro_path is None:
            self._sub_lbl.setText("(저장 안 됨)")
            self.setWindowTitle(f"작업대 · {self._macro.name}{' *' if self._dirty else ''}")
        else:
            self._sub_lbl.setText(self._macro_path.name + (" *" if self._dirty else ""))
            self.setWindowTitle(
                f"작업대 · {self._macro_path.name}{' *' if self._dirty else ''}"
            )

    def _on_new(self) -> None:
        if not self._confirm_discard():
            return
        self._macro = _empty_macro()
        self._macro_path = None
        self._dirty = False
        self._reload_step_list()

    def _on_open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "매크로 열기", str(Path.cwd()),
            "매크로 YAML (*.yaml *.yml)",
        )
        if not path:
            return
        self._load_macro_from_path(Path(path))

    def _load_macro_from_path(self, path: Path) -> None:
        try:
            self._macro = load_macro(path)
        except Exception as e:
            QMessageBox.critical(self, "열기 실패", str(e))
            return
        self._macro_path = path
        self._dirty = False
        self._library.add_recent(path, name=self._macro.name)
        save_library(self._library)
        self.library_panel.set_library(self._library)
        self.library_panel.set_active(str(path))
        self._reload_step_list()

    def _on_save(self) -> None:
        if self._macro_path is None:
            self._on_save_as()
            return
        try:
            save_macro(self._macro, self._macro_path)
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))
            return
        self._dirty = False
        self._library.add_recent(self._macro_path, name=self._macro.name)
        save_library(self._library)
        self.library_panel.set_library(self._library)
        self.library_panel.set_active(str(self._macro_path))
        self._update_title()
        self.statusBar().showMessage("저장됨", 3000)

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "다른 이름으로 저장", str(Path.cwd() / f"{self._macro.name}.yaml"),
            "매크로 YAML (*.yaml *.yml)",
        )
        if not path:
            return
        self._macro_path = Path(path)
        self._on_save()

    def _on_export(self) -> None:
        if self._macro_path is None:
            QMessageBox.warning(self, "내보내기", "먼저 매크로를 저장해 주세요.")
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "매크로 묶음 내보내기",
            str(self._macro_path.with_suffix(".kma")),
            "Keymacro 묶음 (*.kma *.zip)",
        )
        if not target:
            return
        try:
            export_macro(self._macro, self._macro_path.parent, target)
        except Exception as e:
            QMessageBox.critical(self, "내보내기 실패", str(e))
            return
        self.statusBar().showMessage(f"내보냄 → {target}", 5000)

    def _on_import(self) -> None:
        if not self._confirm_discard():
            return
        archive, _ = QFileDialog.getOpenFileName(
            self, "묶음 가져오기", str(Path.cwd()),
            "Keymacro 묶음 (*.kma *.zip)",
        )
        if not archive:
            return
        dest = QFileDialog.getExistingDirectory(
            self, "어디에 풀까요?", str(Path.cwd()),
        )
        if not dest:
            return
        try:
            macro, yaml_path = import_macro(archive, dest)
        except Exception as e:
            QMessageBox.critical(self, "가져오기 실패", str(e))
            return
        self._macro = macro
        self._macro_path = yaml_path
        self._dirty = False
        self._library.add_recent(yaml_path, name=macro.name)
        save_library(self._library)
        self.library_panel.set_library(self._library)
        self.library_panel.set_active(str(yaml_path))
        self._reload_step_list()

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        ans = QMessageBox.question(
            self, "저장하지 않은 변경사항",
            "변경사항을 버릴까요?",
            QMessageBox.Yes | QMessageBox.No,
        )
        return ans == QMessageBox.Yes

    # --- library handlers ------------------------------------------------

    def _on_library_picked(self, path: str) -> None:
        if not self._confirm_discard():
            return
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(
                self, "열기 실패",
                f"파일을 찾을 수 없어요:\n{p}\n\n라이브러리에서 제거할까요?",
            )
            self._library.remove(p)
            save_library(self._library)
            self.library_panel.set_library(self._library)
            return
        self._load_macro_from_path(p)

    def _on_library_pin_toggle(self, path: str) -> None:
        self._library.toggle_pin(path)
        save_library(self._library)
        self.library_panel.set_library(self._library)
        if self._macro_path is not None:
            self.library_panel.set_active(str(self._macro_path))

    def _on_library_remove(self, path: str) -> None:
        self._library.remove(path)
        save_library(self._library)
        self.library_panel.set_library(self._library)
        if self._macro_path is not None:
            self.library_panel.set_active(str(self._macro_path))

    def _on_library_reveal(self, path: str) -> None:
        import subprocess
        import sys as _sys

        try:
            if _sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(Path(path))])
            elif _sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(Path(path))])
            else:
                subprocess.Popen(["xdg-open", str(Path(path).parent)])
        except Exception as e:
            log.warning("could not reveal %s: %s", path, e)

    def _on_library_folder_added(self, folder: str) -> None:
        self._library.add_folder(folder)
        save_library(self._library)
        self.library_panel.set_library(self._library)
        if self._macro_path is not None:
            self.library_panel.set_active(str(self._macro_path))

    def _on_library_folder_removed(self, folder: str) -> None:
        self._library.remove_folder(folder)
        save_library(self._library)
        self.library_panel.set_library(self._library)
        if self._macro_path is not None:
            self.library_panel.set_active(str(self._macro_path))

    # --- web element picker --------------------------------------------

    def _on_pick_web_selector(self, field_key: str) -> None:
        if self._picker_thread is not None and self._picker_thread.isRunning():
            self.statusBar().showMessage("이미 요소를 고르는 중이에요.", 4000)
            return
        config = self._macro.web_session or WebSessionConfig()
        self._picker_field = field_key
        self._picker_thread = PickerThread(config)
        self._picker_thread.picked.connect(self._on_picker_picked)
        self._picker_thread.failed.connect(self._on_picker_failed)
        self._picker_thread.finished.connect(self._cleanup_picker)
        self.statusBar().showMessage(
            "Chrome 탭에서 원하는 요소를 클릭하세요 — Esc로 취소", 0,
        )
        self._picker_thread.start()

    def _on_picker_picked(self, selector: str) -> None:
        if not selector:
            self.statusBar().showMessage("선택 취소됨", 3000)
            return
        if self._picker_field:
            self.form.set_web_selector(self._picker_field, selector)
        self.statusBar().showMessage(f"셀렉터 설정: {selector}", 6000)

    def _on_picker_failed(self, message: str) -> None:
        # If the failure is the standard CDP attach error, offer to auto-launch
        # Chrome instead of dumping a wall of text on the user.
        is_attach_error = (
            "디버그 포트" in message and "연결할 수 없" in message
        ) or "ECONNREFUSED" in message
        if not is_attach_error:
            QMessageBox.warning(self, "요소 선택 실패", message)
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Chrome이 디버그 모드로 안 떠 있어요")
        box.setText(
            "요소를 고르려면 디버그 모드 Chrome이 필요해요.\n"
            "지금 자동으로 띄울까요?\n\n"
            f"※ keymacro 전용 프로필이 사용되며, 첫 실행 시 사이트 로그인만 한 번 해주세요."
        )
        launch_btn = box.addButton("자동으로 띄우기", QMessageBox.AcceptRole)
        cancel_btn = box.addButton("취소", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not launch_btn:
            return
        self.statusBar().showMessage("Chrome 시작 중…", 0)
        ok, msg = ensure_chrome_running()
        self._refresh_chrome_status()
        if not ok:
            QMessageBox.warning(self, "Chrome 시작 실패", msg)
            return
        QMessageBox.information(
            self, "Chrome이 시작됐어요",
            msg + "\n\n로그인이 끝나면 다시 [화면에서 요소 고르기] 를 눌러 주세요.",
        )

    def _cleanup_picker(self) -> None:
        if self._picker_thread is not None:
            self._picker_thread.deleteLater()
        self._picker_thread = None
        self._picker_field = None

    # --- region picker / template capture ------------------------------

    def _pick_region(self) -> None:
        self._region_picker = RegionPickerOverlay()
        self._region_picker.selected.connect(self._on_region_selected)
        self._region_picker.cancelled.connect(self._region_picker.deleteLater)
        self._region_picker.show()

    def _on_region_selected(self, x: int, y: int, w: int, h: int) -> None:
        self.form.set_region(x, y, w, h)
        self._on_form_changed()

    def _capture_template(self) -> None:
        if self._macro_path is None:
            QMessageBox.warning(
                self, "템플릿 캡처",
                "먼저 매크로를 저장해 주세요. 저장된 위치 옆에 templates/ 폴더가 만들어져요.",
            )
            return
        try:
            step = self.form.to_step()
        except Exception as e:
            QMessageBox.warning(self, "템플릿 캡처", f"폼 입력이 잘못됐어요: {e}")
            return
        if not isinstance(step.trigger, ImageTrigger):
            QMessageBox.information(
                self, "템플릿 캡처",
                "트리거를 '이미지가 보이면' 으로 먼저 바꿔 주세요.",
            )
            return
        r = step.trigger.region
        try:
            rel = capture_template(
                self._macro_path.parent,
                (r.x, r.y, r.w, r.h),
                step_id=step.id,
            )
        except Exception as e:
            QMessageBox.critical(self, "캡처 실패", str(e))
            return
        self.form.set_template(rel)
        self.statusBar().showMessage(f"템플릿 저장됨 → {rel}", 5000)

    # --- run lifecycle --------------------------------------------------

    def _on_start(self) -> None:
        if self._runner_thread is not None and self._runner_thread.isRunning():
            return
        if not self._macro.steps:
            QMessageBox.information(self, "실행", "실행할 단계가 없어요.")
            return
        if self._macro_path is None:
            QMessageBox.warning(
                self, "실행",
                "먼저 매크로를 저장해 주세요. 그래야 템플릿 경로가 정확히 풀려요.",
            )
            return
        self._refresh_transport_kind_lookup()
        self._control.reset()
        # Combined observer: QtRunObserver (live GUI signals) + HistoryObserver
        # (SQLite persistence). Both hear every callback.
        combined = MultiObserver(self._observer, self._history.observer())
        self._runner_thread = RunnerThread(
            self._macro, self._macro_path.parent,
            self._control, combined, self._debug_capture_dir,
        )
        self._runner_thread.finished_with_result.connect(self._on_thread_done)
        self.transport.set_running(True)
        self.status_pill.set_state("running", "실행 중")
        self._runner_thread.start()

    def _on_stop(self) -> None:
        if self._runner_thread is None:
            return
        self._control.stop()
        self.status_pill.set_state("idle", "정지 요청…")

    def _on_pause(self) -> None:
        paused = self._control.toggle_pause()
        if paused:
            self.status_pill.set_state("paused", "일시정지")
        else:
            self.status_pill.set_state("running", "실행 중")

    def _on_thread_done(self, _result) -> None:
        self.transport.set_running(False)
        self.status_pill.set_state("idle", "대기 중")
        for i in range(len(self._macro.steps)):
            self.list_panel.set_step_state(i, active=False)
        self._runner_thread = None

    def _on_step_started(self, step_id: str, attempt: int, iteration: int) -> None:
        for i, s in enumerate(self._macro.steps):
            self.list_panel.set_step_state(i, active=(s.id == step_id))
        self.statusBar().showMessage(
            f"단계 {step_id} · 시도 {attempt} · 반복 {iteration + 1}", 0
        )

    def _on_step_ended(self, step_id: str, success: bool, error: str) -> None:
        if not success:
            self.statusBar().showMessage(f"단계 {step_id} 실패: {error}", 6000)

    def _on_run_ended(self, completed: bool, aborted_at: str) -> None:
        msg = "완료" if completed else f"{aborted_at} 에서 중단됨"
        self.statusBar().showMessage(f"실행 {msg}", 8000)
        try:
            self._tray.notify("작업대 · keymacro", f"실행 {msg}")
        except Exception:
            pass

    # --- recorder -------------------------------------------------------

    def _on_record_toggle(self) -> None:
        if self._recorder_ctrl.is_running:
            events = self._recorder_ctrl.stop()
            self._handle_recorded_events(events)
        else:
            self._recorder_ctrl.start()
            self.btn_record.setText("⬛  녹화 정지 (F8)")
            self.statusBar().showMessage(
                "🔴 녹화 중 — 작업 시연하시고, 끝나면 F8 또는 [녹화 정지]", 0,
            )

    def _on_recording_stopped_via_hotkey(self) -> None:
        if not self._recorder_ctrl.is_running:
            # Already stopped through the button path.
            return
        events = self._recorder_ctrl.stop()
        self._handle_recorded_events(events)

    def _handle_recorded_events(self, events) -> None:
        from datetime import datetime

        self.btn_record.setText("●  녹화")
        self.statusBar().clearMessage()
        if not events:
            QMessageBox.information(
                self, "녹화", "기록된 이벤트가 없어요. 다시 시도해 주세요.",
            )
            return
        macro = events_to_macro(
            events, name=f"녹화-{datetime.now():%H%M%S}",
        )
        ans = QMessageBox.question(
            self, "녹화 결과",
            f"이벤트 {len(events)}개 → 단계 {len(macro.steps)}개로 변환됐어요.\n"
            "지금 편집 중인 매크로를 이걸로 바꿀까요?\n"
            "(저장 안 한 변경사항이 있으면 사라집니다)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        if self._dirty and not self._confirm_discard():
            return
        self._macro = macro
        self._macro_path = None
        self._dirty = True
        self._reload_step_list()
        self.statusBar().showMessage(
            f"녹화 완료 — {len(macro.steps)}개 단계. [저장]으로 파일에 저장하세요.",
            8000,
        )

    # --- history dashboard ----------------------------------------------

    def _on_show_history(self) -> None:
        from PySide6.QtWidgets import (
            QDialog, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout,
            QLabel,
        )
        from datetime import datetime

        runs = self._history.list_recent_runs(limit=50)
        dlg = QDialog(self)
        dlg.setWindowTitle("실행 이력 (최근 50건)")
        dlg.resize(720, 480)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel(
            f"{len(runs)}개 실행 · 마지막은 "
            f"{datetime.fromtimestamp(runs[0]['started_at']):%Y-%m-%d %H:%M:%S} "
            if runs else "아직 실행 기록이 없어요."
        )
        title.setStyleSheet(
            f"font-family: 'Noto Sans KR', sans-serif;"
            f"font-size: 14px; font-weight: 600; color: {C['on-surface']};"
        )
        layout.addWidget(title)

        table = QTableWidget(len(runs), 5)
        table.setHorizontalHeaderLabels([
            "시각", "매크로", "결과", "지속(초)", "단계",
        ])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        for i, r in enumerate(runs):
            ts = datetime.fromtimestamp(r["started_at"]).strftime("%m-%d %H:%M:%S")
            outcome = "완료" if r["completed"] else f"중단 ({r['aborted_at']})"
            duration = (
                f"{r['duration_s']:.1f}" if r["duration_s"] else "—"
            )
            steps = f"{r['num_succeeded']} / {r['num_steps']}"
            table.setItem(i, 0, QTableWidgetItem(ts))
            table.setItem(i, 1, QTableWidgetItem(r["macro_name"]))
            item_out = QTableWidgetItem(outcome)
            from PySide6.QtGui import QColor
            if r["completed"]:
                item_out.setForeground(QColor(C["tertiary"]))
            else:
                item_out.setForeground(QColor(C["quaternary"]))
            table.setItem(i, 2, item_out)
            table.setItem(i, 3, QTableWidgetItem(duration))
            table.setItem(i, 4, QTableWidgetItem(steps))
        layout.addWidget(table, 1)

        if self._macro.name:
            stats = self._history.stats_for_macro(self._macro.name)
            if stats["total"]:
                summary = QLabel(
                    f"이 매크로 ({self._macro.name}) 통계 · "
                    f"총 {stats['total']}회 / 성공 {stats['completed']}회 / "
                    f"성공률 {stats['success_rate']*100:.0f}% / "
                    f"평균 {stats['avg_duration_s']:.1f}초"
                )
                summary.setStyleSheet(
                    f"color: {C['on-surface-variant']}; font-size: 12px;"
                )
                layout.addWidget(summary)

        dlg.exec()

    # --- shutdown -------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._runner_thread is not None:
            self._control.stop()
            self._runner_thread.wait(2000)
        if self._picker_thread is not None:
            self._picker_thread.requestInterruption()
            self._picker_thread.wait(1500)
        if self._recorder_ctrl.is_running:
            self._recorder_ctrl.stop()
        try:
            self._hotkeys.stop()
        except Exception:
            pass
        try:
            self._tray.hide()
        except Exception:
            pass
        try:
            self._history.close()
        except Exception:
            pass
        super().closeEvent(event)


def _empty_macro() -> Macro:
    return Macro(name="새-매크로", steps=[])


def _default_step(step_id: str) -> Step:
    return Step(
        id=step_id, name="",
        trigger=TimeTrigger(delay_s=0.0),
        action=ClickAction(x=0, y=0),
    )
