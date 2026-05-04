"""Action recorder — convert live mouse/keyboard input into a macro.

Hooks pynput's global listeners while the user demonstrates a workflow
in their real Chrome (or any app), then converts the captured event
stream into a list of :class:`Step` instances ready to save as YAML.

Design choices that follow from "non-developer using their own laptop":

* The recorder doesn't simulate any input — it strictly observes. So
  recording a 5-step login flow doesn't accidentally trigger anything.
* Every recorded step uses :class:`TimeTrigger` whose ``delay_s`` is the
  elapsed gap from the previous step. The macro replays at the user's
  natural cadence rather than a forced uniform interval.
* Consecutive printable keystrokes are grouped into a single
  :class:`TypeAction`. Two characters with a >0.5s gap break the group —
  so "alice" types as one action, but a long pause then "bob" becomes a
  fresh TypeAction.
* A configurable ``stop_key`` (default ``F8``) terminates the listener
  and is *not* added to the event log.

The resulting macro is a starting point — the user is expected to open
it in the editor and tighten triggers / consolidate steps.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..models import (
    ClickAction,
    KeyAction,
    Macro,
    Step,
    TimeTrigger,
    TypeAction,
)

log = logging.getLogger(__name__)


# Maximum gap between printable keys before they're split into a new
# TypeAction. Tuned to feel like "the user paused to think".
_TYPE_GROUP_GAP_S = 0.5

# Click events arriving within this window are merged into a double-click.
_DOUBLE_CLICK_WINDOW_S = 0.35


@dataclass
class RecordedEvent:
    kind: str          # "click" / "char" / "key" / "scroll"
    t: float           # seconds since recording started
    payload: dict


@dataclass
class Recorder:
    """Lightweight event collector — start, demonstrate, stop, harvest.

    The recorder is *itself* threadsafe but does not own a lock — pynput
    listeners run in their own thread and we trust their callbacks not
    to interleave with :meth:`stop`. The events list grows under that
    assumption; callers who want consistent reads should call
    :meth:`stop` first.
    """

    stop_key: str = "f8"
    on_event: Optional[Callable[[RecordedEvent], None]] = None
    on_stop: Optional[Callable[[], None]] = None

    _events: list[RecordedEvent] = field(default_factory=list)
    _t0: float = 0.0
    _mouse_listener: object = None
    _kb_listener: object = None
    _running: bool = False
    _stop_requested: threading.Event = field(default_factory=threading.Event)

    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        from pynput import keyboard, mouse  # type: ignore[import-not-found]

        self._events = []
        self._t0 = time.monotonic()
        self._stop_requested.clear()

        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._kb_listener = keyboard.Listener(
            on_press=self._on_key_press,
        )
        self._mouse_listener.start()
        self._kb_listener.start()
        self._running = True
        log.info("recorder started")

    def stop(self) -> list[RecordedEvent]:
        if not self._running:
            return list(self._events)
        try:
            if self._mouse_listener is not None:
                self._mouse_listener.stop()
            if self._kb_listener is not None:
                self._kb_listener.stop()
        except Exception:
            log.debug("listener stop raised", exc_info=True)
        self._running = False
        log.info("recorder stopped — %d events", len(self._events))
        return list(self._events)

    # ------------------------------------------------------------------

    @property
    def events(self) -> list[RecordedEvent]:
        return list(self._events)

    @property
    def is_running(self) -> bool:
        return self._running

    # --- pynput callbacks ---------------------------------------------

    def _now(self) -> float:
        return time.monotonic() - self._t0

    def _on_click(self, x, y, button, pressed):
        if not pressed:
            return  # only edge-on-press
        evt = RecordedEvent(
            kind="click", t=self._now(),
            payload={"x": int(x), "y": int(y), "button": button.name},
        )
        self._events.append(evt)
        if self.on_event:
            try:
                self.on_event(evt)
            except Exception:
                log.exception("on_event raised")

    def _on_key_press(self, key):
        # Stop key terminates the listener; do not log it.
        try:
            key_name = getattr(key, "name", None)
        except Exception:
            key_name = None
        if key_name and key_name.lower() == self.stop_key.lower():
            self._stop_requested.set()
            if self.on_stop:
                try:
                    self.on_stop()
                except Exception:
                    log.exception("on_stop raised")
            return False  # signals listener to stop

        # Printable character vs special key
        char = getattr(key, "char", None)
        if isinstance(char, str) and char and char.isprintable():
            evt = RecordedEvent(
                kind="char", t=self._now(), payload={"char": char},
            )
        else:
            evt = RecordedEvent(
                kind="key", t=self._now(),
                payload={"key": key_name or repr(key)},
            )
        self._events.append(evt)
        if self.on_event:
            try:
                self.on_event(evt)
            except Exception:
                log.exception("on_event raised")


# --- Conversion: events → Step list -------------------------------------


def events_to_steps(
    events: list[RecordedEvent],
    *,
    type_group_gap_s: float = _TYPE_GROUP_GAP_S,
    double_click_window_s: float = _DOUBLE_CLICK_WINDOW_S,
    min_delay_s: float = 0.05,
) -> list[Step]:
    """Lower the recorded event stream to a Step list ready for ``Macro``.

    Behaviour:

    * Consecutive printable ``char`` events are grouped into one
      :class:`TypeAction` until the gap exceeds ``type_group_gap_s``.
    * Two ``click`` events on the same (x, y) within
      ``double_click_window_s`` collapse into a ``ClickAction(double=True)``.
    * Wait time between steps is the elapsed gap from the previous
      *committed* step's end-time, clamped to ``min_delay_s``.
    """
    steps: list[Step] = []
    last_t = 0.0
    char_group: list[str] = []
    char_group_start = 0.0
    char_group_last = 0.0
    step_idx = 1

    def _flush_chars():
        nonlocal char_group, step_idx, last_t
        if not char_group:
            return
        text = "".join(char_group)
        wait = max(min_delay_s, char_group_start - last_t)
        steps.append(Step(
            id=f"r{step_idx}", name=f"입력 {text!r}"[:40],
            trigger=TimeTrigger(delay_s=round(wait, 2)),
            action=TypeAction(text=text),
        ))
        step_idx += 1
        last_t = char_group_last
        char_group = []

    i = 0
    while i < len(events):
        e = events[i]
        if e.kind == "char":
            ch = e.payload["char"]
            if char_group and (e.t - char_group_last) > type_group_gap_s:
                _flush_chars()
            if not char_group:
                char_group_start = e.t
            char_group.append(ch)
            char_group_last = e.t
            i += 1
            continue

        # Anything else flushes any in-progress typing.
        _flush_chars()

        if e.kind == "click":
            # Detect double-click by looking ahead.
            x, y, button = e.payload["x"], e.payload["y"], e.payload["button"]
            double = False
            if i + 1 < len(events):
                nxt = events[i + 1]
                if (
                    nxt.kind == "click"
                    and nxt.payload["x"] == x
                    and nxt.payload["y"] == y
                    and nxt.payload["button"] == button
                    and (nxt.t - e.t) <= double_click_window_s
                ):
                    double = True
            wait = max(min_delay_s, e.t - last_t)
            steps.append(Step(
                id=f"r{step_idx}", name=f"{'더블' if double else ''}클릭 ({x},{y})",
                trigger=TimeTrigger(delay_s=round(wait, 2)),
                action=ClickAction(x=x, y=y, button=button, double=double),
            ))
            step_idx += 1
            last_t = nxt.t if double else e.t
            i += 2 if double else 1
            continue

        if e.kind == "key":
            wait = max(min_delay_s, e.t - last_t)
            steps.append(Step(
                id=f"r{step_idx}", name=f"키 {e.payload['key']}",
                trigger=TimeTrigger(delay_s=round(wait, 2)),
                action=KeyAction(keys=e.payload["key"]),
            ))
            step_idx += 1
            last_t = e.t
            i += 1
            continue

        # Unknown kind — skip.
        i += 1

    _flush_chars()
    return steps


def events_to_macro(
    events: list[RecordedEvent], name: str = "녹화-매크로",
) -> Macro:
    return Macro(name=name, description="기록된 매크로", steps=events_to_steps(events))
