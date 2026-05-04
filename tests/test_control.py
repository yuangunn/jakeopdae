"""RunControl: thread-safe stop + pause primitive."""

from __future__ import annotations

from keymacro.core.control import Control, RunControl


def test_protocol_membership():
    c = RunControl()
    assert isinstance(c, Control)


def test_initial_state_is_clear():
    c = RunControl()
    assert not c.is_stopped()
    assert not c.is_paused()


def test_stop_is_sticky():
    c = RunControl()
    c.stop()
    assert c.is_stopped()
    c.stop()
    assert c.is_stopped()


def test_toggle_pause_returns_new_state():
    c = RunControl()
    assert c.toggle_pause() is True
    assert c.is_paused()
    assert c.toggle_pause() is False
    assert not c.is_paused()


def test_reset_clears_both_signals():
    c = RunControl()
    c.stop()
    c.pause()
    c.reset()
    assert not c.is_stopped()
    assert not c.is_paused()


def test_legacy_is_set_alias_tracks_stop():
    c = RunControl()
    assert not c.is_set()
    c.stop()
    assert c.is_set()
