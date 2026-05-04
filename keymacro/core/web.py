"""WebSession — Playwright lifecycle wrapper.

Provides a :class:`WebPage` Protocol so the runner can be unit-tested
against fakes without spinning up a real browser. The default
:class:`PlaywrightSession` is a thin wrapper that:

* attaches to a Chrome started with ``--remote-debugging-port=<port>``,
  reusing the user's profile / cookies / login state, OR
* launches Playwright's bundled Chromium for the duration of the macro.

The launch / connect happens lazily — only when the runner first reaches
a web trigger or action — so macros without web steps never pay the
import cost (or the friendly attach error).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional, Protocol, runtime_checkable

from ..models.web import WebSessionConfig

log = logging.getLogger(__name__)


# --- Protocols (what the runner depends on) ----------------------------------


@runtime_checkable
class WebPage(Protocol):
    def url(self) -> str: ...
    def is_element_state(self, selector: str, state: str, timeout_s: float) -> bool: ...
    def click(
        self, selector: str, *,
        button: str = "left", double: bool = False, force: bool = False,
    ) -> None: ...
    def fill(self, selector: str, text: str, *, delay_ms: int = 0) -> None: ...
    def navigate(self, url: str, *, wait_until: str = "load") -> None: ...
    def screenshot(self, path: str) -> None: ...
    def evaluate(self, expression: str) -> object: ...
    def bring_to_front(self) -> None: ...


@runtime_checkable
class WebSession(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def page(self) -> WebPage: ...


# --- Helpers shared between real + fake --------------------------------------


def url_matches(actual: str, pattern: str, mode: str) -> bool:
    if mode == "exact":
        return actual.strip() == pattern.strip()
    if mode == "regex":
        try:
            return re.search(pattern, actual) is not None
        except re.error:
            log.warning("invalid regex %r", pattern)
            return False
    # "contains" (default)
    return pattern in actual


# --- Friendly attach error ---------------------------------------------------


class AttachError(RuntimeError):
    """Raised when CDP attach fails. Carries a Korean help message."""

    def __init__(self, endpoint: str, original: Exception) -> None:
        msg = (
            f"Chrome 디버그 포트({endpoint}) 에 연결할 수 없어요.\n\n"
            f"Chrome을 다음 명령으로 시작해 주세요:\n"
            f'  "chrome.exe" --remote-debugging-port=9222\n\n'
            f"또는 keymacro chrome-launch 명령을 써도 됩니다.\n\n"
            f"원본 오류: {original!r}"
        )
        super().__init__(msg)
        self.endpoint = endpoint
        self.original = original


# --- Default Playwright-backed implementation ---------------------------------


class PlaywrightPage:
    """:class:`WebPage` Protocol over a Playwright sync ``Page``."""

    def __init__(self, page) -> None:  # playwright.sync_api.Page
        self._page = page

    def url(self) -> str:
        try:
            return self._page.url
        except Exception:
            return ""

    def is_element_state(self, selector: str, state: str, timeout_s: float) -> bool:
        # Playwright's ``locator.wait_for(state=..., timeout=ms)`` raises on
        # timeout; we want a boolean.
        ms = max(1, int(timeout_s * 1000))
        try:
            self._page.locator(selector).wait_for(state=state, timeout=ms)
            return True
        except Exception:
            return False

    def click(
        self, selector: str, *,
        button: str = "left", double: bool = False, force: bool = False,
    ) -> None:
        loc = self._page.locator(selector)
        if double:
            loc.dblclick(button=button, force=force)
        else:
            loc.click(button=button, force=force)

    def fill(self, selector: str, text: str, *, delay_ms: int = 0) -> None:
        loc = self._page.locator(selector)
        if delay_ms > 0:
            loc.click()
            loc.press_sequentially(text, delay=delay_ms)
        else:
            loc.fill(text)

    def navigate(self, url: str, *, wait_until: str = "load") -> None:
        self._page.goto(url, wait_until=wait_until)

    def screenshot(self, path: str) -> None:
        try:
            self._page.screenshot(path=path, full_page=False)
        except Exception:
            log.exception("page screenshot failed")

    def evaluate(self, expression: str) -> object:
        return self._page.evaluate(expression)

    def bring_to_front(self) -> None:
        try:
            self._page.bring_to_front()
        except Exception:
            log.debug("bring_to_front failed", exc_info=True)


class PlaywrightSession:
    """:class:`WebSession` Protocol over Playwright sync API."""

    def __init__(self, config: WebSessionConfig) -> None:
        self.config = config
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._owns_browser = False

    def start(self) -> None:
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        except ImportError as e:
            raise RuntimeError(
                "playwright이 설치되어 있지 않아요. "
                "pip install 'keymacro[web]' 후 'playwright install chromium' 을 실행해 주세요."
            ) from e

        self._pw = sync_playwright().start()
        if self.config.mode == "attach":
            try:
                self._browser = self._pw.chromium.connect_over_cdp(self.config.cdp_endpoint)
            except Exception as e:
                self._cleanup_partial()
                raise AttachError(self.config.cdp_endpoint, e) from e
            self._owns_browser = False
            if not self._browser.contexts:
                self._context = self._browser.new_context()
            else:
                self._context = self._browser.contexts[0]
            if self.config.new_page or not self._context.pages:
                self._page = self._context.new_page()
            else:
                self._page = self._context.pages[0]
                try:
                    self._page.bring_to_front()
                except Exception:
                    pass
        else:
            self._browser = self._pw.chromium.launch(
                headless=self.config.headless,
                channel=self.config.browser_channel or None,
            )
            self._owns_browser = True
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
        log.info(
            "web session started: mode=%s url=%s",
            self.config.mode, self._page.url if self._page else "?",
        )

    def page(self) -> WebPage:
        if self._page is None:
            self.start()
        assert self._page is not None
        return PlaywrightPage(self._page)

    def stop(self) -> None:
        try:
            if self._owns_browser and self._browser is not None:
                self._browser.close()
            elif self._browser is not None and self.config.mode == "attach":
                # Don't close the user's browser; just disconnect.
                try:
                    self._browser.close()
                except Exception:
                    pass
        finally:
            try:
                if self._pw is not None:
                    self._pw.stop()
            except Exception:
                pass
            self._page = None
            self._context = None
            self._browser = None
            self._pw = None

    def _cleanup_partial(self) -> None:
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._pw = None


# --- helpers for the runner --------------------------------------------------


def make_default_session(config: Optional[WebSessionConfig] = None) -> WebSession:
    return PlaywrightSession(config or WebSessionConfig())


def poll_until(
    predicate, *, timeout_s: float, poll_interval_s: float,
    sleep, clock, stop_check,
) -> bool:
    """Poll a synchronous predicate until True or timeout. Used by triggers."""
    deadline = clock() + timeout_s
    probed = False
    while not probed or clock() < deadline:
        stop_check()
        try:
            if predicate():
                return True
        except Exception:
            log.exception("web predicate raised; treating as not-yet")
        probed = True
        if clock() >= deadline:
            break
        sleep(poll_interval_s)
    return False
