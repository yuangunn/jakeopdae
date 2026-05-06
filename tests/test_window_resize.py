"""WindowResizeAction runner integration.

Stubs ``keymacro.core.win_window`` so the test suite doesn't need a
real Windows GUI session — important because CI runs headless and
``user32`` calls would no-op or error.
"""

from __future__ import annotations

import pytest

from keymacro.core import win_window
from keymacro.core.runner import Runner
from keymacro.models import (
    Macro,
    Step,
    TimeTrigger,
    WindowResizeAction,
)

from .conftest import FakeCapturer, FakeInput


@pytest.fixture
def stub_win_window(monkeypatch):
    """Replace win_window with a recorder. Returns the call log."""
    calls: list[tuple] = []

    class FakeInfo:
        def __init__(self, hwnd, title, x=100, y=100, w=800, h=600):
            self.hwnd = hwnd
            self.title = title
            self.x, self.y, self.w, self.h = x, y, w, h

    fake_windows = {
        "Chrome": FakeInfo(101, "Google - Google Chrome"),
        "메모장": FakeInfo(102, "제목 없음 - 메모장"),
    }
    fake_active = FakeInfo(999, "Foreground Window", x=10, y=10, w=400, h=300)

    def fake_is_supported():
        return True

    def fake_find(substr):
        for k, v in fake_windows.items():
            if k.lower() in v.title.lower():
                if substr.lower() in v.title.lower():
                    return v
        return None

    def fake_active_fn():
        return fake_active

    def fake_set_bounds(hwnd, x, y, w, h):
        calls.append(("set_bounds", hwnd, x, y, w, h))
        return True

    def fake_max(hwnd):
        calls.append(("maximize", hwnd))
        return True

    def fake_min(hwnd):
        calls.append(("minimize", hwnd))
        return True

    def fake_restore(hwnd):
        calls.append(("restore", hwnd))
        return True

    def fake_fg(hwnd):
        calls.append(("foreground", hwnd))
        return True

    def fake_fullscreen(hwnd, idx):
        calls.append(("fullscreen", hwnd, idx))
        return True

    monkeypatch.setattr(win_window, "is_supported", fake_is_supported)
    monkeypatch.setattr(win_window, "find_window_by_title", fake_find)
    monkeypatch.setattr(win_window, "get_foreground_window", fake_active_fn)
    monkeypatch.setattr(win_window, "set_window_bounds", fake_set_bounds)
    monkeypatch.setattr(win_window, "maximize_window", fake_max)
    monkeypatch.setattr(win_window, "minimize_window", fake_min)
    monkeypatch.setattr(win_window, "restore_window", fake_restore)
    monkeypatch.setattr(win_window, "bring_to_foreground", fake_fg)
    monkeypatch.setattr(win_window, "fullscreen_on_monitor", fake_fullscreen)
    return calls


def _runner(macro, tmp_path) -> Runner:
    return Runner(
        macro,
        macro_dir=tmp_path,
        capturer=FakeCapturer(),
        input_normal=FakeInput(),
        sleep=lambda s: None,
    )


def test_bounds_mode_calls_set_window_bounds(tmp_path, stub_win_window):
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="resize",
            trigger=TimeTrigger(delay_s=0),
            action=WindowResizeAction(
                title_match="Chrome", mode="bounds",
                x=200, y=300, w=1024, h=768,
            ),
        ),
    ])
    res = _runner(macro, tmp_path).run()
    assert res.completed
    assert ("set_bounds", 101, 200, 300, 1024, 768) in stub_win_window
    # Window should also be brought to foreground after a non-minimize op
    assert ("foreground", 101) in stub_win_window


def test_maximize_mode_calls_maximize(tmp_path, stub_win_window):
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="max",
            trigger=TimeTrigger(delay_s=0),
            action=WindowResizeAction(
                title_match="Chrome", mode="maximize",
            ),
        ),
    ])
    _runner(macro, tmp_path).run()
    assert ("maximize", 101) in stub_win_window


def test_minimize_does_not_bring_to_foreground(tmp_path, stub_win_window):
    """Minimizing then immediately raising the window would defeat the
    purpose; verify we skip the bring_to_foreground hop in that case."""
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="min",
            trigger=TimeTrigger(delay_s=0),
            action=WindowResizeAction(
                title_match="Chrome", mode="minimize",
            ),
        ),
    ])
    _runner(macro, tmp_path).run()
    assert ("minimize", 101) in stub_win_window
    assert all(c[0] != "foreground" for c in stub_win_window)


def test_active_sentinel_uses_foreground_window(tmp_path, stub_win_window):
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="active",
            trigger=TimeTrigger(delay_s=0),
            action=WindowResizeAction(
                title_match="<active>", mode="maximize",
            ),
        ),
    ])
    _runner(macro, tmp_path).run()
    # hwnd 999 is the foreground sentinel
    assert ("maximize", 999) in stub_win_window


def test_fullscreen_monitor_passes_index(tmp_path, stub_win_window):
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="fs",
            trigger=TimeTrigger(delay_s=0),
            action=WindowResizeAction(
                title_match="Chrome",
                mode="fullscreen_monitor",
                monitor_index=1,
            ),
        ),
    ])
    _runner(macro, tmp_path).run()
    assert ("fullscreen", 101, 1) in stub_win_window


def test_missing_window_raises_step_error(tmp_path, stub_win_window):
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="ghost",
            trigger=TimeTrigger(delay_s=0),
            action=WindowResizeAction(
                title_match="NoSuchWindow",
                mode="maximize",
            ),
            on_failure="skip",
        ),
    ])
    res = _runner(macro, tmp_path).run()
    # on_failure=skip means the run completes despite the error
    assert res.completed
    # No maximize call happened
    assert all(c[0] != "maximize" for c in stub_win_window)


def test_unsupported_platform_raises(tmp_path, monkeypatch):
    """When ``win_window.is_supported()`` returns False (macOS/Linux),
    the action surfaces a Korean explainer rather than silently
    no-opping."""
    monkeypatch.setattr(win_window, "is_supported", lambda: False)
    macro = Macro(name="m", steps=[
        Step(
            id="s1", name="x",
            trigger=TimeTrigger(delay_s=0),
            action=WindowResizeAction(
                title_match="Chrome", mode="maximize",
            ),
            on_failure="skip",
        ),
    ])
    res = _runner(macro, tmp_path).run()
    assert res.completed  # skip swallowed the platform error
    # Step did fail though — check StepResult
    sr = res.step_results[0]
    assert not sr.success
    assert "Windows" in (sr.error or "")
