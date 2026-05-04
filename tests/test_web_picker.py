"""Web element picker — orchestration sanity (no real browser needed).

The selector-ranking JS runs inside the page so we don't unit-test it
here; instead we drive ``pick_element_selector`` against a fake page
that returns rigged ``evaluate`` results, asserting the polling loop
behaves correctly under each terminal condition (result / cancel /
timeout / page navigation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from keymacro.core.web_picker import pick_element_selector


@dataclass
class FakePage:
    queue: list[object] = field(default_factory=list)
    """List of dicts to return on each subsequent ``evaluate`` call after
    the initial injection. The injection itself returns ``None``."""
    seen_expressions: list[str] = field(default_factory=list)
    raise_after: Optional[int] = None

    def evaluate(self, expression: str) -> object:
        self.seen_expressions.append(expression)
        # First call is the injection script — returns None.
        if len(self.seen_expressions) == 1:
            return None
        if (
            self.raise_after is not None
            and len(self.seen_expressions) >= self.raise_after
        ):
            raise RuntimeError("page navigated")
        if not self.queue:
            return {"active": True, "result": None, "cancelled": False}
        return self.queue.pop(0)

    def url(self) -> str:
        return ""

    def is_element_state(self, *_a, **_kw) -> bool:
        return False

    def click(self, *_a, **_kw) -> None:
        pass

    def fill(self, *_a, **_kw) -> None:
        pass

    def navigate(self, *_a, **_kw) -> None:
        pass

    def screenshot(self, *_a, **_kw) -> None:
        pass

    def bring_to_front(self) -> None:
        pass


@dataclass
class FakeSession:
    page_obj: FakePage = field(default_factory=FakePage)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def page(self) -> FakePage:
        return self.page_obj


def test_pick_returns_selector_on_user_click():
    page = FakePage(
        queue=[
            {"active": True, "result": None, "cancelled": False},
            {"active": True, "result": None, "cancelled": False},
            {"active": False, "result": "role=button[name=\"학습하기\"]", "cancelled": False},
        ],
    )
    sess = FakeSession(page_obj=page)
    sel = pick_element_selector(sess, timeout_s=2.0, poll_interval_s=0.0)
    assert sel == 'role=button[name="학습하기"]'
    # Injection script + at least one poll evaluate
    assert len(page.seen_expressions) >= 2


def test_pick_returns_none_on_cancel():
    page = FakePage(
        queue=[
            {"active": True, "result": None, "cancelled": False},
            {"active": False, "result": None, "cancelled": True},
        ],
    )
    sess = FakeSession(page_obj=page)
    sel = pick_element_selector(sess, timeout_s=2.0, poll_interval_s=0.0)
    assert sel is None


def test_pick_returns_none_when_picker_torn_down():
    page = FakePage(
        queue=[
            {"active": False, "result": None, "cancelled": False},
        ],
    )
    sess = FakeSession(page_obj=page)
    sel = pick_element_selector(sess, timeout_s=2.0, poll_interval_s=0.0)
    assert sel is None


def test_pick_handles_navigation_gracefully():
    """If ``page.evaluate`` raises (e.g. context destroyed by navigation),
    the picker returns None instead of crashing the GUI thread."""
    page = FakePage(raise_after=2)  # 1=inject, 2=poll → raise
    sess = FakeSession(page_obj=page)
    sel = pick_element_selector(sess, timeout_s=2.0, poll_interval_s=0.0)
    assert sel is None


def test_pick_times_out():
    # Always return "active, no result" so polling never terminates.
    page = FakePage()
    sess = FakeSession(page_obj=page)
    sel = pick_element_selector(sess, timeout_s=0.05, poll_interval_s=0.01)
    assert sel is None
    # Cleanup eval should have been called as well.
    assert any("cleanup" in e for e in page.seen_expressions)


def test_injection_script_executes_first():
    page = FakePage(queue=[{"active": False, "cancelled": True, "result": None}])
    sess = FakeSession(page_obj=page)
    pick_element_selector(sess, timeout_s=2.0, poll_interval_s=0.0)
    # The first evaluate call must be the IIFE that installs the picker.
    first = page.seen_expressions[0]
    assert "__keymacroPicker" in first
    assert "(()" in first or "(function" in first
