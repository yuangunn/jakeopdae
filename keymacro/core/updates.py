"""Check GitHub Releases for a newer version of keymacro.

Pure stdlib (``urllib``) — no ``requests`` dependency. Used both by
the ``keymacro check-updates`` CLI subcommand and (optionally) the
GUI's startup toast.

Network failures, missing repos, rate-limit responses all return
``None`` — the calling code shows a single Korean line and moves on
rather than blocking the user from doing actual work.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

_TIMEOUT_S = 6.0
_USER_AGENT = "keymacro-update-check"


def current_version() -> str:
    from .. import __version__
    return __version__


# ---------------------------------------------------------------------------


@dataclass
class UpdateInfo:
    current: str
    latest_tag: str
    is_newer: bool
    html_url: str
    assets: list[dict]


# ---------------------------------------------------------------------------


def check_for_updates(repo: str = "yuangunn/jakeopdae") -> Optional[UpdateInfo]:
    """Query ``api.github.com`` for the latest release of ``repo``.

    Returns an :class:`UpdateInfo` or ``None`` on any error. Never
    raises — release-notes / network blips shouldn't crash a CLI
    subcommand.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        req = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": _USER_AGENT,
            },
        )
        with urlopen(req, timeout=_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError) as e:
        log.info("update check failed: %s", e)
        return None
    except Exception:
        log.exception("unexpected error during update check")
        return None

    latest_tag = (data.get("tag_name") or "").strip()
    if not latest_tag:
        return None

    cur = current_version()
    is_newer = _semver_gt(latest_tag, cur)

    assets = []
    for a in data.get("assets") or []:
        assets.append({
            "name": a.get("name"),
            "url": a.get("browser_download_url"),
            "size_mb": (a.get("size") or 0) / 1024 / 1024,
        })

    return UpdateInfo(
        current=cur,
        latest_tag=latest_tag,
        is_newer=is_newer,
        html_url=data.get("html_url") or "",
        assets=assets,
    )


# ---------------------------------------------------------------------------


_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[.-](.*))?$")


def _semver_gt(a: str, b: str) -> bool:
    """``True`` when ``a`` is a strictly newer semver than ``b``.

    Handles ``v`` prefix, ignores any trailing ``-rc1`` / ``+sha`` style
    pre-release suffix (treats them as equal). Returns ``False`` when
    either side fails to parse — fail-closed so users don't get a
    spurious "new version!" toast on a malformed tag.
    """
    ma = _SEMVER.match(a.strip())
    mb = _SEMVER.match(b.strip())
    if not ma or not mb:
        return False
    return tuple(int(ma.group(i)) for i in (1, 2, 3)) > tuple(
        int(mb.group(i)) for i in (1, 2, 3)
    )
