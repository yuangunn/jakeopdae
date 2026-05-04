"""Create Windows ``.lnk`` shortcuts via the WScript.Shell COM API.

Pure stdlib — no extra dependency on ``pywin32`` / ``winshell``.
Internally shells out to PowerShell once and lets it drive the
``WScript.Shell`` ProgID. Slow (~150 ms per shortcut) but reliable on
every Windows where PowerShell is present (i.e. every supported
Windows since 7).

For PyInstaller ``--onefile`` distributions this finds the *real* exe
the user double-clicks, not the per-launch extracted python interpreter
inside ``%LOCALAPPDATA%\\Temp\\_MEI…``. ``sys.executable`` already
points at the right binary in that mode, so we don't have to do
anything special.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def desktop_dir() -> Path:
    """Return the current user's Desktop directory.

    Honours OneDrive / 한국어 데스크탑 redirects via ``USERPROFILE`` —
    a hard-coded ``~/Desktop`` would miss those.
    """
    user = os.environ.get("USERPROFILE") or str(Path.home())
    candidates = [
        Path(user) / "Desktop",
        Path(user) / "OneDrive" / "Desktop",
        Path(user) / "OneDrive" / "바탕 화면",
        Path(user) / "바탕 화면",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    # Fall back to creating ``%USERPROFILE%\Desktop``.
    fallback = Path(user) / "Desktop"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def keymacro_target() -> tuple[str, list[str]]:
    """Return ``(target, args)`` for launching the GUI.

    Picks the right entry point depending on whether we're running
    inside a PyInstaller bundle (``sys.frozen``) or a regular Python
    install. In bundle mode the exe knows its own subcommands; in dev
    mode we use ``pythonw.exe -m keymacro`` to avoid the console pop-up.
    """
    if getattr(sys, "frozen", False):
        return sys.executable, ["gui"]

    # Find pythonw.exe next to the active python.exe so the shortcut
    # doesn't open a black console window.
    py = sys.executable
    pyw = Path(py).parent / "pythonw.exe"
    interpreter = str(pyw) if pyw.exists() else py
    return interpreter, ["-m", "keymacro", "gui"]


def create_shortcut(
    path: Path,
    target: str,
    args: list[str],
    *,
    description: str = "",
    icon: Optional[str] = None,
    working_dir: Optional[str] = None,
) -> bool:
    """Create a Windows ``.lnk`` at ``path`` pointing to ``target``.

    Returns ``True`` on success. Errors are logged and surfaced as
    ``False`` so callers can chain "create N shortcuts, report which
    succeeded".
    """
    path = path.with_suffix(".lnk")
    args_str = " ".join(_quote(a) for a in args)
    icon_loc = icon or f"{target},0"
    work = working_dir or str(Path(target).parent)

    # Use ``-Command`` with a here-string so we don't have to escape
    # every nested quote for PowerShell's parser.
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"{_ps_quote(str(path))}); "
        f"$s.TargetPath = {_ps_quote(target)}; "
        f"$s.Arguments = {_ps_quote(args_str)}; "
        f"$s.WorkingDirectory = {_ps_quote(work)}; "
        f"$s.IconLocation = {_ps_quote(icon_loc)}; "
        + (f"$s.Description = {_ps_quote(description)}; " if description else "")
        + "$s.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        log.info("created shortcut: %s", path)
        return True
    except subprocess.CalledProcessError as e:
        log.error("powershell failed creating %s: %s", path, e.stderr)
        return False
    except subprocess.TimeoutExpired:
        log.error("powershell timed out creating %s", path)
        return False


def _quote(s: str) -> str:
    """Quote an argument for ``Arguments`` of a Windows shortcut.

    Windows uses ``CommandLineToArgvW`` to parse ``Arguments`` at launch
    time, so we use the standard ``"…"`` quoting + backslash escape for
    embedded quotes. Most shortcuts won't hit anything weird because we
    only ever pass plain-ASCII subcommand names.
    """
    if " " in s or '"' in s:
        return '"' + s.replace('"', '\\"') + '"'
    return s


def _ps_quote(s: str) -> str:
    """PowerShell single-quoted literal — no expansion, only ``''``
    needs escaping by doubling."""
    return "'" + s.replace("'", "''") + "'"


# --- high-level helpers used by the CLI ------------------------------------


def create_default_shortcut() -> Path:
    """Create ``작업대.lnk`` on the desktop pointing at the GUI. Returns
    the .lnk path (whether or not it succeeded — caller checks
    existence)."""
    target, args = keymacro_target()
    out = desktop_dir() / "작업대.lnk"
    create_shortcut(
        out, target, args,
        description="작업대 — keymacro GUI",
    )
    return out


def create_chrome_debug_shortcut() -> Path:
    """Create ``작업대 Chrome (디버그).lnk`` that runs
    ``keymacro chrome-launch`` so the user has a one-click way to bring
    up the dedicated debug-mode Chrome whenever they need web macros."""
    if getattr(sys, "frozen", False):
        target, args = sys.executable, ["chrome-launch"]
    else:
        py = sys.executable
        pyw = Path(py).parent / "pythonw.exe"
        target = str(pyw) if pyw.exists() else py
        args = ["-m", "keymacro", "chrome-launch"]
    out = desktop_dir() / "작업대 Chrome (디버그).lnk"
    create_shortcut(
        out, target, args,
        description="작업대 — keymacro 전용 디버그 Chrome 띄우기",
    )
    return out
