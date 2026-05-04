"""GUI entry point.

Imported lazily by ``keymacro.cli`` so the optional PySide6 dependency is
only required when the user actually launches the GUI.

The QSS theme is applied at the QApplication level (``setStyleSheet`` on
``QApplication.instance()``) so dialogs and popups inherit it without
each widget tree having to re-apply.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def _stable_log_dir() -> Path:
    """Pick a log directory that doesn't depend on cwd.

    Preference order: ``%LOCALAPPDATA%\\keymacro\\logs`` on Windows, else
    ``~/.local/share/keymacro/logs``. Ensures every GUI launch's log file
    lands in the same place regardless of where the binary was invoked
    from.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "keymacro" / "logs"
    return Path.home() / ".local" / "share" / "keymacro" / "logs"


def run_gui(
    initial_macro: Optional[Path] = None,
    debug_capture_dir: Optional[Path] = None,
    *,
    log_dir: Optional[Path] = None,
) -> int:
    from PySide6.QtWidgets import QApplication

    from ..core.logger import setup_logging
    from .fonts import load_bundled_fonts
    from .main_window import MainWindow
    from .theme import apply_theme

    setup_logging(verbose=False, log_dir=log_dir or _stable_log_dir())

    app = QApplication.instance() or QApplication(sys.argv)
    # Load bundled fonts BEFORE applying the QSS so style rules
    # referencing "Noto Sans KR" resolve to our shipped TTFs.
    load_bundled_fonts()
    apply_theme(app)
    win = MainWindow(debug_capture_dir=debug_capture_dir)

    # Close the PyInstaller splash screen as soon as the main window is
    # ready to render. Three failure modes to swallow:
    #   - regular Python:    ``pyi_splash`` doesn't exist (ImportError)
    #   - PyInstaller without ``Splash``: ``_PYI_SPLASH_IPC`` env var
    #     missing → module-level KeyError on import
    #   - splash already closed by the bootloader: RuntimeError
    try:
        import pyi_splash  # type: ignore[import-not-found]

        pyi_splash.close()
    except Exception:
        pass
    if initial_macro is not None and initial_macro.exists():
        try:
            # Use the same load path as the Open button so the macro lands
            # in 최근 and the active row is highlighted in the sidebar.
            win._load_macro_from_path(initial_macro)  # type: ignore[attr-defined]
        except Exception:
            import logging
            logging.getLogger(__name__).exception("could not preload macro")
    win.show()
    return app.exec()
