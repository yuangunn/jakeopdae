"""Shared pytest fixtures and fakes used across the test suite.

The runner depends on a :class:`Capturer` and an :class:`Input`. Both are
Protocols, which lets us swap in pure-Python fakes without monkey-patching.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class FakeCapturer:
    """A capturer that returns a queue of pre-baked frames.

    If the queue is exhausted, ``default`` is returned indefinitely; if no
    default is set, a black image of the requested size is produced.
    """

    frames: list[np.ndarray] = field(default_factory=list)
    default: np.ndarray | None = None
    calls: list[tuple[int, int, int, int]] = field(default_factory=list)

    def grab(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        self.calls.append((x, y, w, h))
        if self.frames:
            return self.frames.pop(0)
        if self.default is not None:
            return self.default
        return np.zeros((h, w, 3), dtype=np.uint8)

    def close(self) -> None:
        pass


@dataclass
class FakeInput:
    """An input backend that records every event for assertion."""

    events: list[tuple] = field(default_factory=list)

    def click(self, x: int, y: int, button: str = "left", double: bool = False) -> None:
        self.events.append(("click", int(x), int(y), button, bool(double)))

    def key(self, keys: str) -> None:
        self.events.append(("key", keys))

    def type_text(self, text: str, interval_s: float = 0.0) -> None:
        self.events.append(("type", text, float(interval_s)))

    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_s: float = 0.3,
        button: str = "left",
    ) -> None:
        self.events.append(("drag", int(x1), int(y1), int(x2), int(y2), button))


class CountingClock:
    """A monotonic clock that advances by ``step`` on every call.

    Useful for asserting deterministic behaviour around timeouts and the
    macro-level runtime cap.
    """

    def __init__(self, start: float = 0.0, step: float = 0.01) -> None:
        self.t = start
        self.step = step

    def __call__(self) -> float:
        v = self.t
        self.t += self.step
        return v


def solid_bgr(h: int, w: int, color: tuple[int, int, int]) -> np.ndarray:
    """Build a solid-color BGR image."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = color
    return img


def textured_bgr(h: int, w: int, seed: int = 0) -> np.ndarray:
    """Build a deterministic textured BGR image (so multi-scale tests don't
    devolve into ambiguous solid-color matches)."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
