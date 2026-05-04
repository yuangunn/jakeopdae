"""Sequential macro runner.

Executes a :class:`Macro` step by step. Each step waits for its trigger
and then runs its action; the success / failure flow is governed by
``on_failure`` and ``on_success_goto`` on the step. ``repeat`` runs the
trigger+action pair multiple times in a row before advancing.

External signals (stop, pause) come in via a :class:`Control` (typically
:class:`~keymacro.core.control.RunControl`). Observation hooks
(:class:`RunObserver`) let GUIs and tray icons mirror runner state without
the runner needing to know about them.

Dependencies (capturer, input backends, sleep, clock, control, observer)
are injected via the constructor so the runner is exhaustively unit-
testable without touching real screens or input devices.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Protocol, Union, runtime_checkable

import cv2  # type: ignore[import-not-found]
import numpy as np

from ..models.action import (
    Action,
    ClickAction,
    DragAction,
    KeyAction,
    TypeAction,
    WaitAction,
)
from ..models.macro import Macro
from ..models.ocr import ExtractTextAction, OcrTextTrigger
from ..models.schedule import ScheduleTrigger, seconds_until_next
from ..models.step import Step
from ..models.hybrid import HybridImageTrigger
from ..models.trigger import ImageTrigger, PixelColorTrigger, TimeTrigger, Trigger
from ..models.web import (
    WebClickAction,
    WebElementVisibleTrigger,
    WebNavigateAction,
    WebTypeAction,
    WebUrlTrigger,
)
from .browser_url import read_browser_url, url_matches as browser_url_matches
from .capture import Capturer, make_default_capturer
from .control import Control
from .input import Input, make_input
from .ocr import TesseractMissing, read_text as ocr_read_text, text_matches
from .variables import substitute
from .matcher import MatchResult, match_template
from .observer import RunObserver, null_observer
from .web import WebSession, make_default_session, url_matches

log = logging.getLogger(__name__)


# --- Result types -----------------------------------------------------------------


@dataclass
class StepResult:
    step_id: str
    success: bool
    error: Optional[str] = None
    match: Optional[MatchResult] = None
    attempts: int = 1
    iterations_completed: int = 0
    duration_s: float = 0.0


@dataclass
class RunResult:
    macro_name: str
    completed: bool = False
    aborted_at: Optional[str] = None
    step_results: list[StepResult] = field(default_factory=list)


# --- Stop / pause primitives ------------------------------------------------------


@runtime_checkable
class StopFlag(Protocol):
    """Legacy single-bit stop signal. Kept for backwards compatibility with
    early tests; new code should prefer :class:`Control`."""

    def is_set(self) -> bool: ...


class _NeverStop:
    def is_set(self) -> bool:
        return False


class _StopRequested(Exception):
    """Sentinel raised when :class:`Control` reports a stop during a wait."""


_StopSignal = Union[Control, StopFlag]


# --- Runner -----------------------------------------------------------------------


class Runner:
    def __init__(
        self,
        macro: Macro,
        macro_dir: Union[str, Path],
        *,
        capturer: Optional[Capturer] = None,
        input_normal: Optional[Input] = None,
        input_raw: Optional[Input] = None,
        web_session: Optional[WebSession] = None,
        control: Optional[Control] = None,
        stop_flag: Optional[StopFlag] = None,
        observer: Optional[RunObserver] = None,
        debug_capture_dir: Optional[Union[str, Path]] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.macro = macro
        self.macro_dir = Path(macro_dir)
        self._capturer = capturer
        self._input_normal = input_normal
        self._input_raw = input_raw
        self._web_session = web_session
        self._web_started = False
        self._control = control
        self._stop = stop_flag or _NeverStop()
        self._observer = observer or null_observer()
        self._debug_capture_dir = (
            Path(debug_capture_dir) if debug_capture_dir is not None else None
        )
        self._sleep = sleep
        self._clock = clock
        self._template_cache: dict[str, np.ndarray] = {}
        self._last_match: Optional[MatchResult] = None
        # Runtime variables — initialised from macro spec, mutated by
        # ExtractTextAction. Available to every action's string fields
        # via ``${name}`` substitution.
        self._vars: dict[str, str] = dict(macro.variables or {})

    # --- lazy dependency construction -----------------------------------------

    def _capturer_or_default(self) -> Capturer:
        if self._capturer is None:
            self._capturer = make_default_capturer()
        return self._capturer

    def _input(self, mode: str) -> Input:
        if mode == "raw":
            if self._input_raw is None:
                self._input_raw = make_input("raw")
            return self._input_raw
        if self._input_normal is None:
            self._input_normal = make_input("normal")
        return self._input_normal

    def _web(self) -> WebSession:
        if self._web_session is None:
            self._web_session = make_default_session(self.macro.web_session)
        if not self._web_started:
            self._web_session.start()
            self._web_started = True
        return self._web_session

    def _load_template(self, rel_path: str) -> np.ndarray:
        if rel_path in self._template_cache:
            return self._template_cache[rel_path]
        path = (self.macro_dir / rel_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"template not found: {path}")
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"failed to load template: {path}")
        self._template_cache[rel_path] = img
        return img

    # --- stop / pause helpers -------------------------------------------------

    def _should_stop(self) -> bool:
        if self._control is not None:
            return self._control.is_stopped()
        return self._stop.is_set()

    def _wait_while_paused(self) -> None:
        if self._control is None:
            return
        while self._control.is_paused() and not self._control.is_stopped():
            self._sleep(0.05)

    def _check_stop_or_pause(self) -> None:
        self._wait_while_paused()
        if self._should_stop():
            raise _StopRequested()

    # --- public API -----------------------------------------------------------

    def run(self) -> RunResult:
        result = RunResult(macro_name=self.macro.name)
        self._observer.on_run_start(self.macro.name)
        try:
            if not self.macro.steps:
                result.completed = True
                return result

            # If any step uses web, start the session up front so failures
            # surface before we waste time on earlier non-web steps.
            if self._uses_web():
                try:
                    self._web()
                except Exception as e:
                    log.error("could not start web session: %s", e)
                    result.aborted_at = self.macro.steps[0].id
                    return result

            steps_by_id = {s.id: s for s in self.macro.steps}
            for s in self.macro.steps:
                if s.on_success_goto and s.on_success_goto not in steps_by_id:
                    raise ValueError(
                        f"step {s.id!r} has on_success_goto={s.on_success_goto!r} "
                        "which does not exist"
                    )

            run_start = self._clock()
            current_id: Optional[str] = self.macro.steps[0].id

            while current_id is not None:
                if self._should_stop():
                    result.aborted_at = current_id
                    log.info("stop requested at step %s", current_id)
                    break
                elapsed = self._clock() - run_start
                if elapsed > self.macro.max_total_runtime_s:
                    result.aborted_at = current_id
                    log.warning(
                        "max_total_runtime_s exceeded (%.2fs > %.2fs)",
                        elapsed, self.macro.max_total_runtime_s,
                    )
                    break

                step = steps_by_id[current_id]
                sr = self._run_step(step)
                result.step_results.append(sr)
                self._observer.on_step_end(step.id, sr.success, sr.match, sr.error)

                if sr.success:
                    current_id = step.on_success_goto or self._next_id(step)
                    continue

                if step.on_failure == "skip":
                    current_id = self._next_id(step)
                    continue

                result.aborted_at = step.id
                break

            result.completed = result.aborted_at is None
            return result
        finally:
            self._observer.on_run_end(result.completed, result.aborted_at)
            if self._web_started and self._web_session is not None:
                try:
                    self._web_session.stop()
                except Exception:
                    log.exception("web session stop raised")
                self._web_started = False

    def _uses_web(self) -> bool:
        for s in self.macro.steps:
            if isinstance(s.trigger, (WebElementVisibleTrigger, WebUrlTrigger)):
                return True
            if isinstance(s.action, (WebClickAction, WebTypeAction, WebNavigateAction)):
                return True
        return False

    # --- step execution -------------------------------------------------------

    def _next_id(self, step: Step) -> Optional[str]:
        ids = [s.id for s in self.macro.steps]
        idx = ids.index(step.id)
        return ids[idx + 1] if idx + 1 < len(ids) else None

    def _run_step(self, step: Step) -> StepResult:
        """Run a step's trigger+action ``step.repeat`` times, with retries.

        Outer loop: iterations (``step.repeat``).
        Inner loop: attempts (``1 + step.retry_count`` when ``on_failure='retry'``).
        """
        start = self._clock()
        attempts_per_iter = 1 + (step.retry_count if step.on_failure == "retry" else 0)
        last_err: Optional[str] = None
        last_match: Optional[MatchResult] = None
        total_attempts = 0
        completed_iters = 0

        for iteration in range(step.repeat):
            iter_succeeded = False
            for attempt in range(1, attempts_per_iter + 1):
                total_attempts += 1
                if self._should_stop():
                    return StepResult(
                        step.id, False, error="stopped",
                        attempts=total_attempts,
                        iterations_completed=completed_iters,
                        duration_s=self._clock() - start,
                    )
                self._observer.on_step_start(step.id, attempt, iteration)
                log.info(
                    "step %s [%s] iter %d/%d attempt %d/%d",
                    step.id, step.name, iteration + 1, step.repeat,
                    attempt, attempts_per_iter,
                )

                try:
                    trigger_outcome = self._wait_trigger(step)
                except _StopRequested:
                    return StepResult(
                        step.id, False, error="stopped",
                        attempts=total_attempts,
                        iterations_completed=completed_iters,
                        duration_s=self._clock() - start,
                    )

                if trigger_outcome is None:
                    last_err = "trigger_timeout"
                    self._save_failure_capture(step)
                    continue

                match = (
                    trigger_outcome
                    if isinstance(trigger_outcome, MatchResult)
                    else None
                )
                if match is not None:
                    self._last_match = match
                    last_match = match

                try:
                    self._do_action(step.action, match)
                except _StopRequested:
                    return StepResult(
                        step.id, False, error="stopped",
                        attempts=total_attempts,
                        iterations_completed=completed_iters,
                        duration_s=self._clock() - start,
                    )
                except Exception as e:  # noqa: BLE001
                    last_err = f"action_failed: {e!r}"
                    log.exception("action failed in step %s", step.id)
                    self._save_failure_capture(step)
                    continue

                iter_succeeded = True
                break  # break attempts loop, advance iteration

            if not iter_succeeded:
                return StepResult(
                    step.id, False, error=last_err or "unknown",
                    match=last_match, attempts=total_attempts,
                    iterations_completed=completed_iters,
                    duration_s=self._clock() - start,
                )
            completed_iters += 1

        return StepResult(
            step.id, True, match=last_match,
            attempts=total_attempts,
            iterations_completed=completed_iters,
            duration_s=self._clock() - start,
        )

    # --- triggers -------------------------------------------------------------

    def _wait_trigger(self, step: Step):
        trigger: Trigger = step.trigger
        if isinstance(trigger, TimeTrigger):
            self._interruptible_sleep(trigger.delay_s)
            return True
        if isinstance(trigger, ImageTrigger):
            return self._poll_image(step.id, trigger)
        if isinstance(trigger, PixelColorTrigger):
            return self._poll_pixel(trigger)
        if isinstance(trigger, WebElementVisibleTrigger):
            return self._poll_web_element(trigger)
        if isinstance(trigger, WebUrlTrigger):
            return self._poll_web_url(trigger)
        if isinstance(trigger, HybridImageTrigger):
            return self._poll_hybrid_image(step.id, trigger)
        if isinstance(trigger, OcrTextTrigger):
            return self._poll_ocr(step.id, trigger)
        if isinstance(trigger, ScheduleTrigger):
            return self._wait_schedule(trigger)
        raise TypeError(f"unknown trigger: {type(trigger).__name__}")

    def _wait_schedule(self, trig: ScheduleTrigger) -> bool:
        """Sleep until the next ``HH:MM`` match on an allowed weekday.

        We chunk the wait into 1-second slices so stop/pause stay
        responsive — a user shouldn't have to wait for a 6-hour sleep
        to end before F10 takes effect.
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        # Grace window: if the scheduled slot was just missed (cron drift),
        # fire immediately.
        h, m = (int(x) for x in trig.at.split(":"))
        latest = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if 0 <= (now - latest).total_seconds() <= trig.grace_s and \
           now.weekday() in trig.weekdays:
            log.info("schedule trigger fired within grace window")
            return True

        wait_s = seconds_until_next(trig.at, trig.weekdays, now=now)
        eta = now + timedelta(seconds=wait_s)
        log.info(
            "schedule: waiting %.0fs until %s (%s)",
            wait_s, eta.isoformat(timespec="minutes"),
            ["월", "화", "수", "목", "금", "토", "일"][eta.weekday()],
        )
        self._interruptible_sleep(wait_s)
        return True

    def _poll_image(
        self, step_id: str, trig: ImageTrigger
    ) -> Optional[MatchResult]:
        template = self._load_template(trig.template)
        cap = self._capturer_or_default()
        deadline = self._clock() + trig.timeout_s
        best = MatchResult.not_found()
        probed = False

        while not probed or self._clock() < deadline:
            self._check_stop_or_pause()
            haystack = cap.grab(
                trig.region.x, trig.region.y, trig.region.w, trig.region.h
            )
            res = match_template(
                haystack, template,
                region_origin=(trig.region.x, trig.region.y),
                confidence=trig.confidence,
                multi_scale=trig.multi_scale,
                scale_min=trig.scale_min,
                scale_max=trig.scale_max,
                scale_steps=trig.scale_steps,
            )
            probed = True
            self._observer.on_match_attempt(step_id, res.confidence, res.found)
            if res.found:
                log.info(
                    "image match at (%d,%d) score=%.3f",
                    res.center_x, res.center_y, res.confidence,
                )
                return res
            if res.confidence > best.confidence:
                best = res
            if self._clock() >= deadline:
                break
            self._interruptible_sleep(trig.poll_interval_s)

        log.info("image trigger timed out (best score=%.3f)", best.confidence)
        return None

    def _poll_pixel(self, trig: PixelColorTrigger) -> Optional[bool]:
        cap = self._capturer_or_default()
        deadline = self._clock() + trig.timeout_s
        probed = False
        target_r, target_g, target_b = trig.rgb
        tol = trig.tolerance

        while not probed or self._clock() < deadline:
            self._check_stop_or_pause()
            img = cap.grab(trig.x, trig.y, 1, 1)
            b, g, r = int(img[0, 0, 0]), int(img[0, 0, 1]), int(img[0, 0, 2])
            probed = True
            if (
                abs(r - target_r) <= tol
                and abs(g - target_g) <= tol
                and abs(b - target_b) <= tol
            ):
                return True
            if self._clock() >= deadline:
                break
            self._interruptible_sleep(trig.poll_interval_s)
        return None

    def _poll_hybrid_image(
        self, step_id: str, trig: HybridImageTrigger,
    ) -> Optional[MatchResult]:
        """Image match guarded by the active browser tab's URL.

        Reads the URL via :func:`read_browser_url` (Windows UIA / window
        title) — no CDP, so the user's regular Chrome works. When the URL
        guard fails, the trigger doesn't waste a frame capture; it just
        re-polls the URL until either the URL matches (then it falls
        through to image matching) or the timeout elapses.
        """
        template = self._load_template(trig.template)
        cap = self._capturer_or_default()
        deadline = self._clock() + trig.timeout_s
        best = MatchResult.not_found()
        probed = False

        while not probed or self._clock() < deadline:
            self._check_stop_or_pause()

            url = read_browser_url(trig.browser)
            url_ok = browser_url_matches(url, trig.url_contains, trig.url_mode)
            if not url_ok:
                probed = True
                if self._clock() >= deadline:
                    break
                self._interruptible_sleep(trig.poll_interval_s)
                continue

            haystack = cap.grab(
                trig.region.x, trig.region.y, trig.region.w, trig.region.h,
            )
            res = match_template(
                haystack, template,
                region_origin=(trig.region.x, trig.region.y),
                confidence=trig.confidence,
                multi_scale=trig.multi_scale,
                scale_min=trig.scale_min,
                scale_max=trig.scale_max,
                scale_steps=trig.scale_steps,
            )
            probed = True
            self._observer.on_match_attempt(step_id, res.confidence, res.found)
            if res.found:
                log.info(
                    "hybrid match (URL %r) at (%d,%d) score=%.3f",
                    url, res.center_x, res.center_y, res.confidence,
                )
                return res
            if res.confidence > best.confidence:
                best = res
            if self._clock() >= deadline:
                break
            self._interruptible_sleep(trig.poll_interval_s)

        log.info(
            "hybrid trigger timed out (best score=%.3f, last URL=%r)",
            best.confidence, read_browser_url(trig.browser),
        )
        return None

    def _poll_ocr(self, step_id: str, trig: OcrTextTrigger) -> Optional[bool]:
        """OCR a region until the recognised text matches the pattern.

        Tesseract is several orders of magnitude slower than pixel
        matching, so the poll interval is intentionally larger than for
        image triggers. We tolerate missing/broken Tesseract by raising
        ``TesseractMissing`` once at the first probe — the runner's
        retry/skip semantics turn that into a normal step failure.
        """
        cap = self._capturer_or_default()
        deadline = self._clock() + trig.timeout_s
        probed = False
        last_text = ""
        while not probed or self._clock() < deadline:
            self._check_stop_or_pause()
            haystack = cap.grab(
                trig.region.x, trig.region.y, trig.region.w, trig.region.h,
            )
            try:
                last_text = ocr_read_text(haystack, language=trig.language)
            except TesseractMissing:
                # Re-raise so the runner's outer catch logs and aborts the step.
                raise
            except Exception:
                log.exception("OCR call raised; treating as no-match")
                last_text = ""
            probed = True
            if text_matches(
                last_text, trig.text, mode=trig.mode,
                case_sensitive=trig.case_sensitive,
            ):
                self._observer.on_match_attempt(step_id, 1.0, True)
                log.info("OCR matched %r in step %s", trig.text, step_id)
                return True
            self._observer.on_match_attempt(step_id, 0.0, False)
            if self._clock() >= deadline:
                break
            self._interruptible_sleep(trig.poll_interval_s)

        log.info(
            "OCR trigger timed out (last text len=%d, looking for %r)",
            len(last_text), trig.text,
        )
        return None

    def _poll_web_element(self, trig: WebElementVisibleTrigger) -> Optional[bool]:
        page = self._web().page()
        deadline = self._clock() + trig.timeout_s
        probed = False
        while not probed or self._clock() < deadline:
            self._check_stop_or_pause()
            if trig.url_contains and trig.url_contains not in page.url():
                probed = True
                if self._clock() >= deadline:
                    break
                self._interruptible_sleep(trig.poll_interval_s)
                continue
            # Use a short per-poll timeout so we stay interruptible.
            per_poll = min(trig.poll_interval_s, max(0.0, deadline - self._clock()))
            ok = page.is_element_state(
                trig.selector, trig.state, max(0.05, per_poll),
            )
            probed = True
            if ok:
                log.info("web element matched: %s", trig.selector)
                return True
            if self._clock() >= deadline:
                break
        log.info("web element trigger timed out: %s", trig.selector)
        return None

    def _poll_web_url(self, trig: WebUrlTrigger) -> Optional[bool]:
        page = self._web().page()
        deadline = self._clock() + trig.timeout_s
        probed = False
        while not probed or self._clock() < deadline:
            self._check_stop_or_pause()
            if url_matches(page.url(), trig.pattern, trig.mode):
                return True
            probed = True
            if self._clock() >= deadline:
                break
            self._interruptible_sleep(trig.poll_interval_s)
        return None

    def _interruptible_sleep(self, total_s: float) -> None:
        if total_s <= 0:
            self._check_stop_or_pause()
            return
        end = self._clock() + total_s
        while True:
            now = self._clock()
            if now >= end:
                return
            self._check_stop_or_pause()
            chunk = min(0.05, end - now)
            self._sleep(chunk)

    # --- actions --------------------------------------------------------------

    def _do_action(self, action: Action, match: Optional[MatchResult]) -> None:
        if isinstance(action, WaitAction):
            self._interruptible_sleep(action.duration_s)
            return

        if isinstance(action, ClickAction):
            inp = self._input(action.input_mode)
            if action.relative_to_match and match is not None:
                x = match.center_x + action.x
                y = match.center_y + action.y
            else:
                x = action.x
                y = action.y
            inp.click(int(x), int(y), action.button, action.double)
            return

        if isinstance(action, KeyAction):
            inp = self._input(action.input_mode)
            inp.key(self._sub(action.keys))
            return

        if isinstance(action, TypeAction):
            inp = self._input("normal")
            inp.type_text(self._sub(action.text), action.interval_s)
            return

        if isinstance(action, DragAction):
            inp = self._input(action.input_mode)
            inp.drag(
                int(action.x1), int(action.y1),
                int(action.x2), int(action.y2),
                action.duration_s, action.button,
            )
            return

        if isinstance(action, WebClickAction):
            self._web().page().click(
                self._sub(action.selector),
                button=action.button,
                double=action.double,
                force=action.force,
            )
            return

        if isinstance(action, WebTypeAction):
            self._web().page().fill(
                self._sub(action.selector),
                self._sub(action.text),
                delay_ms=action.delay_ms,
            )
            return

        if isinstance(action, WebNavigateAction):
            self._web().page().navigate(
                self._sub(action.url), wait_until=action.wait_until,
            )
            return

        if isinstance(action, ExtractTextAction):
            cap = self._capturer_or_default()
            haystack = cap.grab(
                action.region.x, action.region.y,
                action.region.w, action.region.h,
            )
            text = ocr_read_text(haystack, language=action.language)
            if action.strip:
                text = " ".join(text.split())
            self._vars[action.variable] = text
            log.info("extracted ${%s}=%r", action.variable, text[:60])
            return

        raise TypeError(f"unknown action: {type(action).__name__}")

    # --- variable helper ----------------------------------------------------

    def _sub(self, text: str) -> str:
        """Apply ``${var}`` substitution against the runtime variables."""
        return substitute(text, self._vars)

    # --- failure capture (Phase 5) -------------------------------------------

    def _save_failure_capture(self, step: Step) -> None:
        """When the trigger times out, dump what the runner saw so the user
        can adjust the region / template / confidence / selector offline.

        For image triggers we save the captured screen region; for web
        triggers we save the full Playwright page screenshot.
        """
        try:
            self._observer.on_failure_capture(step.id, _placeholder_image())
            if self._debug_capture_dir is None:
                return
            self._debug_capture_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            if isinstance(step.trigger, ImageTrigger):
                cap = self._capturer_or_default()
                haystack = cap.grab(
                    step.trigger.region.x, step.trigger.region.y,
                    step.trigger.region.w, step.trigger.region.h,
                )
                path = self._debug_capture_dir / f"{ts}_{step.id}.png"
                cv2.imwrite(str(path), haystack)
                self._observer.on_failure_capture(step.id, haystack)
                log.info("saved failure capture: %s", path)
                return

            if isinstance(
                step.trigger, (WebElementVisibleTrigger, WebUrlTrigger)
            ) and self._web_started and self._web_session is not None:
                path = self._debug_capture_dir / f"{ts}_{step.id}_page.png"
                self._web_session.page().screenshot(str(path))
                log.info("saved web failure screenshot: %s", path)
                return
        except Exception:
            log.exception("failed to save failure capture")


def _placeholder_image() -> np.ndarray:
    return np.zeros((1, 1, 3), dtype=np.uint8)
