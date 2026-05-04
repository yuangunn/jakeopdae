"""Phase 1 + 2 verification — shortcut quoting + update-check semver math.

Live PowerShell calls and HTTPS requests aren't run here — only the
pure-Python helpers that have non-trivial logic.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from keymacro.core.shortcut import _ps_quote, _quote, desktop_dir, keymacro_target
from keymacro.core.updates import _semver_gt, check_for_updates


# --- shortcut.py ---------------------------------------------------------


def test_ps_quote_doubles_internal_apostrophe():
    assert _ps_quote("plain") == "'plain'"
    assert _ps_quote("Helios's path") == "'Helios''s path'"
    assert _ps_quote("") == "''"


def test_arg_quoting_handles_spaces_and_quotes():
    assert _quote("simple") == "simple"
    assert _quote("with space") == '"with space"'
    assert _quote('with"quote') == '"with\\"quote"'


def test_desktop_dir_returns_existing_directory(tmp_path, monkeypatch):
    """``desktop_dir`` must return *some* writable directory; we don't
    pin which redirected path it picks because OneDrive / Korean
    Windows / plain Windows all lay it out differently."""
    p = desktop_dir()
    assert p.exists() and p.is_dir()


def test_keymacro_target_dev_mode():
    """In dev mode (no ``sys.frozen``), the target should be a Python
    interpreter and the args should pass ``-m keymacro gui``."""
    target, args = keymacro_target()
    # Dev environment — args are ``["-m", "keymacro", "gui"]``.
    assert "gui" in args
    assert target.lower().endswith(("python.exe", "pythonw.exe"))


# --- updates.py ----------------------------------------------------------


def test_semver_gt_basics():
    assert _semver_gt("0.2.0", "0.1.0")
    assert _semver_gt("v0.2.0", "0.1.0")     # v prefix
    assert _semver_gt("1.0.0", "0.99.99")
    assert not _semver_gt("0.1.0", "0.1.0")  # equal -> not newer
    assert not _semver_gt("0.1.0", "0.2.0")  # older
    assert not _semver_gt("garbage", "0.1.0")  # unparseable -> false (fail-closed)


def test_semver_gt_with_suffixes():
    # Suffixes are ignored, so v0.1.0-rc1 == v0.1.0 (not strictly newer)
    assert not _semver_gt("0.1.0-rc1", "0.1.0")


def test_check_for_updates_handles_offline(monkeypatch):
    """Missing network must return None, not raise.

    NOTE: ``updates.py`` does ``from urllib.request import urlopen`` so
    we patch the *bound* name ``keymacro.core.updates.urlopen`` rather
    than ``urllib.request.urlopen`` — patching the original wouldn't
    intercept calls that go through the imported reference.
    """
    from urllib.error import URLError

    def boom(*_a, **_kw):
        raise URLError("no network")

    with patch("keymacro.core.updates.urlopen", side_effect=boom):
        result = check_for_updates("yuangunn/jakeopdae")
    assert result is None


def test_check_for_updates_parses_response(monkeypatch):
    """Happy path with a stubbed API response."""
    fake_payload = {
        "tag_name": "v9.9.9",
        "html_url": "https://example.com/release/v9.9.9",
        "assets": [
            {"name": "jakeopdae.exe", "browser_download_url": "https://x", "size": 270 * 1024 * 1024},
        ],
    }

    class FakeResp:
        def read(self):
            import json
            return json.dumps(fake_payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    with patch("keymacro.core.updates.urlopen", return_value=FakeResp()):
        info = check_for_updates("ignored/repo")

    assert info is not None
    assert info.latest_tag == "v9.9.9"
    assert info.is_newer is True   # v9.9.9 > current 0.1.0
    assert info.assets[0]["size_mb"] == pytest.approx(270.0, rel=0.01)


def test_check_for_updates_reports_not_newer(monkeypatch):
    """When latest matches current version, ``is_newer`` is False."""
    from keymacro.core.updates import current_version

    fake_payload = {
        "tag_name": current_version(),
        "html_url": "https://example.com",
        "assets": [],
    }

    class FakeResp:
        def read(self):
            import json
            return json.dumps(fake_payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    with patch("keymacro.core.updates.urlopen", return_value=FakeResp()):
        info = check_for_updates("ignored/repo")

    assert info is not None
    assert not info.is_newer
