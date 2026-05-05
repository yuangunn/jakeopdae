"""Minimal HTTP client — stdlib only, stub-able for tests.

Why not the ``requests`` package: shipping in PyInstaller adds ~3 MB
for one feature, and ``urllib.request`` covers everything HttpAction
needs (verbs, headers, body, timeout, response.text). The interface
here is narrow on purpose so a fancier backend can replace it later
without changing the runner.

Public API:
    request(method, url, *, headers, body, timeout_s) -> str
        Returns the response body decoded as text. Raises
        :class:`HttpError` on 4xx/5xx and on transport failures
        (network, DNS, TLS).

Stubbing in tests:
    Replace ``_REQUEST`` with a function of the same shape — the
    runner imports through this module rather than directly.
"""

from __future__ import annotations

from typing import Callable, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request


class HttpError(RuntimeError):
    """Wraps both HTTP-status failures (4xx/5xx) and transport-level
    errors (DNS / TLS / connection refused) into one type so the
    runner can route them through ``on_failure`` uniformly."""

    def __init__(self, message: str, *, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


def _do_request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str],
    body: str,
    timeout_s: float,
) -> str:
    data = body.encode("utf-8") if body else None
    req = urllib_request.Request(url, data=data, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib_request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                return raw.decode(charset)
            except (UnicodeDecodeError, LookupError):
                return raw.decode("utf-8", errors="replace")
    except urllib_error.HTTPError as e:
        # Read the body so the caller can inspect it. Failure is fine —
        # some servers return empty bodies on 4xx/5xx.
        try:
            body_txt = e.read().decode("utf-8", errors="replace")
        except Exception:
            body_txt = ""
        raise HttpError(
            f"HTTP {e.code} {e.reason}: {body_txt[:200]}",
            status=e.code,
        ) from e
    except urllib_error.URLError as e:
        raise HttpError(f"network error: {e.reason}") from e
    except (TimeoutError, OSError) as e:
        raise HttpError(f"transport error: {e}") from e


# Module-level alias so tests can monkeypatch ``http_client._REQUEST``.
_REQUEST: Callable[..., str] = _do_request


def request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    body: str = "",
    timeout_s: float = 10.0,
) -> str:
    """Make an HTTP request, returning the response body as text.

    Tests replace ``_REQUEST`` to avoid touching the network."""
    return _REQUEST(
        method, url,
        headers=headers or {},
        body=body,
        timeout_s=timeout_s,
    )
