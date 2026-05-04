"""Screen capture utilities.

The :class:`Capturer` Protocol is what the runner depends on, so tests can
swap in a fake. The default implementation uses ``mss`` because it is the
fastest cross-platform capture library — typically 10–30 ms per frame on
Windows.

Returned arrays are BGR (OpenCV's expected order), with the alpha channel
from the underlying BGRA buffer dropped.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class Capturer(Protocol):
    """Anything that can hand back a BGR ndarray of a screen rectangle."""

    def grab(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """Return a BGR image of the screen rectangle (x, y, w, h)."""
        ...

    def close(self) -> None:
        """Release any held resources. Idempotent."""
        ...


class MSSCapturer:
    """Default :class:`Capturer` powered by the ``mss`` library."""

    def __init__(self) -> None:
        # Lazy import keeps the test suite importable on machines without mss.
        import mss  # type: ignore[import-not-found]

        self._sct = mss.mss()

    def grab(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        bbox = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
        raw = np.array(self._sct.grab(bbox))  # H x W x 4 (BGRA)
        # mss returns BGRA; OpenCV expects BGR. Drop the alpha plane in-place.
        return raw[:, :, :3]

    def close(self) -> None:
        try:
            self._sct.close()
        except Exception:
            pass


def make_default_capturer() -> Capturer:
    """Construct the default :class:`Capturer` (mss-based)."""
    return MSSCapturer()
