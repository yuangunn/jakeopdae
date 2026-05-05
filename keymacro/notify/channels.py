"""Notification channels for ``NotifyAction``.

Three providers, all webhook-based so no per-user OAuth dance:

    - **telegram**  ``token`` + ``chat_id`` → POST sendMessage
    - **slack**     incoming webhook URL → POST chat payload
    - **discord**   webhook URL → POST chat payload
    - **kakao_work** webhook URL → POST simple text (KakaoWork format)

Why no native KakaoTalk: the consumer KakaoTalk app has no public API
for sending messages to oneself. Workarounds (메시지 보내기 API,
"나에게 보내기") require OAuth + opt-in. KakaoWork (the corporate
client) does have a webhook surface, and most Korean offices already
use Slack or Telegram for ops notifications, so we cover those three
without forcing users through a Kakao Developers app.

Tests stub `_REQUEST` (same pattern as `core/http_client`) to avoid
the network.
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request

log = logging.getLogger(__name__)


class NotifyError(RuntimeError):
    """Wraps both transport and provider-side failures so callers can
    route through the runner's on_failure machinery uniformly."""


def _do_post(
    url: str,
    *,
    headers: Mapping[str, str],
    body: bytes,
    timeout_s: float,
) -> str:
    req = urllib_request.Request(url, data=body, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib_request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except urllib_error.HTTPError as e:
        try:
            body_txt = e.read().decode("utf-8", errors="replace")
        except Exception:
            body_txt = ""
        raise NotifyError(
            f"HTTP {e.code} {e.reason}: {body_txt[:200]}",
        ) from e
    except urllib_error.URLError as e:
        raise NotifyError(f"network error: {e.reason}") from e
    except (TimeoutError, OSError) as e:
        raise NotifyError(f"transport error: {e}") from e


# Module-level alias so tests can monkeypatch ``channels._POST``.
_POST: Callable[..., str] = _do_post


def post(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    body: bytes = b"",
    timeout_s: float = 10.0,
) -> str:
    return _POST(url, headers=headers or {}, body=body, timeout_s=timeout_s)


# --- providers --------------------------------------------------------------


def send_telegram(
    *, token: str, chat_id: str, text: str, timeout_s: float = 10.0,
) -> str:
    if not token.strip() or not chat_id.strip():
        raise NotifyError("telegram requires token + chat_id")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }).encode("utf-8")
    return post(
        url,
        headers={"Content-Type": "application/json"},
        body=payload,
        timeout_s=timeout_s,
    )


def send_slack(
    *, webhook_url: str, text: str, timeout_s: float = 10.0,
) -> str:
    if not webhook_url.strip():
        raise NotifyError("slack requires webhook_url")
    payload = json.dumps({"text": text}).encode("utf-8")
    return post(
        webhook_url,
        headers={"Content-Type": "application/json"},
        body=payload,
        timeout_s=timeout_s,
    )


def send_discord(
    *, webhook_url: str, text: str, timeout_s: float = 10.0,
) -> str:
    """Discord webhook payload uses ``content`` rather than ``text``."""
    if not webhook_url.strip():
        raise NotifyError("discord requires webhook_url")
    payload = json.dumps({"content": text}).encode("utf-8")
    return post(
        webhook_url,
        headers={"Content-Type": "application/json"},
        body=payload,
        timeout_s=timeout_s,
    )


def send_kakao_work(
    *, webhook_url: str, text: str, timeout_s: float = 10.0,
) -> str:
    """KakaoWork incoming webhook accepts a simple ``{text: ...}``
    payload — same shape as Slack so we keep the body identical."""
    if not webhook_url.strip():
        raise NotifyError("kakao_work requires webhook_url")
    payload = json.dumps({"text": text}).encode("utf-8")
    return post(
        webhook_url,
        headers={"Content-Type": "application/json"},
        body=payload,
        timeout_s=timeout_s,
    )
