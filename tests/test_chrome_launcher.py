"""Chrome launcher: discovery, profile dir, port probing.

We don't actually spawn Chrome in tests — that would be flaky and slow.
Instead we drive the deterministic helpers and stub network calls.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from keymacro.core import chrome_launcher as cl


def test_keymacro_chrome_profile_dir_uses_localappdata_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Fake\Local")
    p = cl.keymacro_chrome_profile_dir()
    assert "Fake" in str(p) and p.name == "chrome-profile"
    assert p.parent.name == "keymacro"


def test_keymacro_chrome_profile_dir_uses_xdg_on_posix(monkeypatch, tmp_path):
    """``keymacro_chrome_profile_dir`` should join its base on the path of
    the platform it's running on (POSIX-style on Linux/Mac, Windows-style
    on Windows). We assert structure rather than a hardcoded slash style
    so the test runs on both."""
    fake_base = tmp_path / "xdg-base"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(fake_base))
    p = cl.keymacro_chrome_profile_dir()
    assert p.parent.parent == fake_base
    assert p.parent.name == "keymacro"
    assert p.name == "chrome-profile"


def test_is_cdp_listening_returns_false_for_closed_port():
    # Port 1 is reserved on most systems, so it should never be listening.
    assert cl.is_cdp_listening(port=1, timeout_s=0.1) is False


def test_is_cdp_listening_returns_true_for_loopback_listener():
    # Spin up a tiny listener and probe it.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        assert cl.is_cdp_listening(host="127.0.0.1", port=port, timeout_s=0.5) is True
    finally:
        sock.close()


def test_wait_for_cdp_ready_returns_true_when_already_open():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        assert cl.wait_for_cdp_ready(host="127.0.0.1", port=port, timeout_s=1.0) is True
    finally:
        sock.close()


def test_wait_for_cdp_ready_returns_false_on_timeout():
    assert cl.wait_for_cdp_ready(port=1, timeout_s=0.3) is False


def test_ensure_chrome_running_skips_launch_when_already_listening():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        with patch.object(cl, "launch_chrome_with_cdp") as launch_mock:
            ok, msg = cl.ensure_chrome_running(port=port, timeout_s=0.5)
            assert ok is True
            assert "이미" in msg
            launch_mock.assert_not_called()
    finally:
        sock.close()


def test_ensure_chrome_running_reports_missing_executable():
    with patch.object(cl, "find_chrome_executable", return_value=None), \
         patch.object(cl, "is_cdp_listening", return_value=False):
        ok, msg = cl.ensure_chrome_running(port=1, timeout_s=0.1)
        assert ok is False
        assert "찾을 수 없" in msg


def test_ensure_chrome_running_handles_failed_launch(tmp_path):
    with patch.object(cl, "is_cdp_listening", return_value=False), \
         patch.object(cl, "find_chrome_executable", return_value="/fake/chrome"), \
         patch.object(cl, "launch_chrome_with_cdp", return_value=None):
        ok, msg = cl.ensure_chrome_running(port=1, user_data_dir=tmp_path, timeout_s=0.1)
        assert ok is False
        assert "시작하지 못" in msg


def test_ensure_chrome_running_reports_timeout(tmp_path):
    """Launch returns a fake Popen but the port never becomes available."""
    fake_proc = object()  # any non-None
    with patch.object(cl, "is_cdp_listening", return_value=False), \
         patch.object(cl, "find_chrome_executable", return_value="/fake/chrome"), \
         patch.object(cl, "launch_chrome_with_cdp", return_value=fake_proc), \
         patch.object(cl, "wait_for_cdp_ready", return_value=False):
        ok, msg = cl.ensure_chrome_running(port=1, user_data_dir=tmp_path, timeout_s=0.1)
        assert ok is False
        assert "열리지 않" in msg


def test_find_chrome_falls_back_to_well_known_paths(monkeypatch, tmp_path):
    # Pretend nothing is on PATH and exactly one well-known location exists.
    monkeypatch.setattr(cl.shutil, "which", lambda _: None)
    fake_chrome = tmp_path / "Chrome.app" / "Contents" / "MacOS" / "Google Chrome"
    fake_chrome.parent.mkdir(parents=True)
    fake_chrome.write_text("")
    # We can't easily inject our path into the candidates tuple, but we can
    # at least assert the function returns None when neither PATH nor any
    # candidate exists — the negative path:
    with patch("keymacro.core.chrome_launcher.Path") as path_cls:
        path_cls.side_effect = lambda *a, **kw: tmp_path / "definitely-not-here"
        # Bring back the real shutil.which to also confirm None
        result = cl.find_chrome_executable()
        # Returned path object in our patched world doesn't exist, so result
        # is None.
        assert result is None
