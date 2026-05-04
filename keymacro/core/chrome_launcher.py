"""Helpers for launching Chrome with the remote-debugging port.

Centralises the logic so both the CLI ``chrome-launch`` subcommand and
the GUI's [🌐 Chrome 시작] toolbar button (and the picker's smart
recovery dialog) reuse the same code path.

Chrome refuses to enable ``--remote-debugging-port`` on an *already
running* instance, so we always launch with our own ``--user-data-dir``.
That gives the user a clean, isolated Chrome profile that persists
across sessions (cookies, logins, extensions installed there) without
touching their normal browsing.
"""

from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_CDP_PORT = 9222


def find_chrome_executable() -> Optional[str]:
    """Locate ``chrome.exe`` (or ``google-chrome`` / ``chromium``) on disk.

    Probes ``PATH`` first, then well-known install locations on each OS.
    Returns ``None`` if nothing is found — caller should surface that as
    a helpful error rather than crashing.
    """
    for name in ("chrome", "chrome.exe", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found

    candidates = (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
        ),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
    )
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def keymacro_chrome_profile_dir() -> Path:
    """The user-data-dir keymacro launches Chrome with — kept stable so
    the user only has to log in once."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(
            Path.home() / ".local" / "share"
        )
    return Path(base) / "keymacro" / "chrome-profile"


def is_cdp_listening(
    host: str = "localhost",
    port: int = DEFAULT_CDP_PORT,
    timeout_s: float = 0.4,
) -> bool:
    """``True`` when we can open a TCP connection to the debug port.

    Cheap probe — a real attach goes through Playwright. Used as a
    pre-flight to avoid spawning Chrome when one is already serving.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def wait_for_cdp_ready(
    host: str = "localhost",
    port: int = DEFAULT_CDP_PORT,
    timeout_s: float = 15.0,
    poll_interval_s: float = 0.4,
) -> bool:
    """Block up to ``timeout_s`` waiting for the debug port to listen.

    Caller should call this after launching Chrome so the next attach
    attempt has a chance of succeeding.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if is_cdp_listening(host, port, timeout_s=0.25):
            return True
        time.sleep(poll_interval_s)
    return False


def launch_chrome_with_cdp(
    port: int = DEFAULT_CDP_PORT,
    user_data_dir: Optional[Path] = None,
    *,
    extra_args: Optional[list[str]] = None,
) -> Optional[subprocess.Popen]:
    """Spawn Chrome detached with the debug port set.

    Returns the ``Popen`` handle on success, ``None`` if Chrome can't be
    located. Doesn't wait for the port — call :func:`wait_for_cdp_ready`
    after this if you intend to attach immediately.
    """
    exe = find_chrome_executable()
    if exe is None:
        log.warning("could not find Chrome executable")
        return None

    profile = user_data_dir or keymacro_chrome_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)

    cmd = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if extra_args:
        cmd.extend(extra_args)

    log.info("launching Chrome: %s", " ".join(cmd))
    # On Windows we want the process truly detached so closing the
    # keymacro CLI doesn't kill Chrome. ``CREATE_NEW_PROCESS_GROUP`` plus
    # closing stdio handles is the canonical way.
    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    return subprocess.Popen(
        cmd,
        creationflags=creationflags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def ensure_chrome_running(
    port: int = DEFAULT_CDP_PORT,
    user_data_dir: Optional[Path] = None,
    timeout_s: float = 15.0,
) -> tuple[bool, str]:
    """Idempotently bring up a debug-mode Chrome.

    Returns ``(ok, message)``. ``ok=True`` means the port is now
    listening — either it already was, or we just launched Chrome and
    waited for it to come up. ``ok=False`` includes a Korean explainer
    suitable for showing to the user.
    """
    if is_cdp_listening("localhost", port):
        return True, f"이미 Chrome이 디버그 모드(포트 {port})로 실행 중이에요."

    if find_chrome_executable() is None:
        return False, (
            "Chrome 실행 파일을 찾을 수 없어요.\n\n"
            "Chrome을 설치했다면 직접 다음 명령으로 시작해 주세요:\n"
            f'  "chrome.exe" --remote-debugging-port={port}'
        )

    proc = launch_chrome_with_cdp(port=port, user_data_dir=user_data_dir)
    if proc is None:
        return False, "Chrome을 시작하지 못했어요."

    if wait_for_cdp_ready(port=port, timeout_s=timeout_s):
        return True, (
            f"Chrome이 디버그 모드(포트 {port})로 시작됐어요.\n"
            f"새 창에서 사이트에 로그인한 뒤 다시 시도해 주세요."
        )
    return False, (
        f"Chrome이 시작됐지만 디버그 포트({port})가 {timeout_s:.0f}초 안에 "
        "열리지 않았어요. 잠시 후 다시 시도해 주세요."
    )
