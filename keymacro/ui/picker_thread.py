"""QThread wrapper around the element picker.

Playwright's sync API must be driven from a single thread, so the picker
gets its own short-lived ``WebSession`` that's started, used, and stopped
all within one ``run()`` call. The main GUI thread stays responsive
while the user picks.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QThread, Signal

from ..core.web import AttachError, make_default_session
from ..core.web_picker import pick_element_selector
from ..models.web import WebSessionConfig

log = logging.getLogger(__name__)


class PickerThread(QThread):
    picked = Signal(str)   # selector or empty string on cancel
    failed = Signal(str)   # human-readable error message

    def __init__(
        self,
        config: Optional[WebSessionConfig] = None,
        timeout_s: float = 60.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config or WebSessionConfig()
        self._timeout_s = timeout_s

    def run(self) -> None:  # noqa: D401 — QThread override
        session = None
        try:
            session = make_default_session(self._config)
            session.start()
            try:
                session.page().bring_to_front()
            except Exception:
                log.debug("bring_to_front failed", exc_info=True)
            selector = pick_element_selector(session, timeout_s=self._timeout_s)
            self.picked.emit(selector or "")
        except AttachError as e:
            self.failed.emit(str(e))
        except RuntimeError as e:
            # Playwright not installed, browser launch failed, etc.
            self.failed.emit(str(e))
        except Exception as e:
            log.exception("picker failed")
            self.failed.emit(f"요소 선택 중 오류가 났어요:\n{e!r}")
        finally:
            if session is not None:
                try:
                    session.stop()
                except Exception:
                    log.debug("session stop raised", exc_info=True)
