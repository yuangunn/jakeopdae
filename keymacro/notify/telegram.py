"""Telegram notification helpers.

Mirrors the KTX worker's ``notifier.py``: take a token + chat id, POST to
the Bot API. The ``session`` parameter exists so tests can inject a fake
HTTP session and assert on the payload without needing network access.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Protocol, runtime_checkable

from ..core.runner import RunResult, StepResult

log = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"


@runtime_checkable
class _PostSession(Protocol):
    def post(
        self,
        url: str,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any: ...


class TelegramNotifier:
    """Lightweight Telegram bot client.

    Construct once with the bot token + target chat id and call
    :meth:`send` for plain messages or :meth:`notify_run_result` for a
    pre-formatted run summary.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        session: Optional[_PostSession] = None,
        timeout_s: float = 10.0,
    ) -> None:
        if not token or not chat_id:
            raise ValueError("token and chat_id are required")
        self._token = token
        self._chat_id = chat_id
        self._session = session
        self._timeout_s = timeout_s

    def _http(self) -> _PostSession:
        if self._session is not None:
            return self._session
        import requests  # type: ignore[import-not-found]

        self._session = requests.Session()
        return self._session

    def send(self, text: str, *, parse_mode: Optional[str] = None) -> bool:
        """Send a plain message. Returns ``True`` on HTTP 2xx."""
        url = f"{_API_BASE}/bot{self._token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self._chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            resp = self._http().post(url, json=payload, timeout=self._timeout_s)
            ok = 200 <= getattr(resp, "status_code", 500) < 300
            if not ok:
                log.warning(
                    "telegram send failed: status=%s body=%s",
                    getattr(resp, "status_code", "?"),
                    getattr(resp, "text", "?"),
                )
            return ok
        except Exception:
            log.exception("telegram send raised")
            return False

    def notify_run_result(self, result: RunResult) -> bool:
        return self.send(build_run_summary_message(result))


def build_run_summary_message(result: RunResult) -> str:
    """Format a :class:`RunResult` into a compact Telegram message.

    Pure function so tests can pin the exact wording without going through
    the HTTP layer.
    """
    status = "completed" if result.completed else f"aborted at {result.aborted_at}"
    lines = [f"keymacro: {result.macro_name} — {status}"]
    for sr in _summarize_steps(result.step_results):
        lines.append(sr)
    return "\n".join(lines)


def _summarize_steps(steps: Iterable[StepResult]) -> list[str]:
    out: list[str] = []
    for sr in steps:
        flag = "OK" if sr.success else "FAIL"
        extra = f" err={sr.error}" if sr.error else ""
        out.append(
            f"  [{flag}] {sr.step_id} attempts={sr.attempts} "
            f"iters={sr.iterations_completed} duration={sr.duration_s:.2f}s{extra}"
        )
    return out
