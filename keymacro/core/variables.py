"""Macro-variable substitution.

Strings in actions can reference macro variables using ``${name}``
syntax. The runner maintains a runtime variables dict (initialised from
``Macro.variables``) and ``ExtractTextAction`` writes new entries into
it, so a later step's ``TypeAction.text``, ``WebNavigateAction.url``,
etc. can use ``${name}`` and have it replaced with the captured value.

Unknown variable references are left as-is (rather than raising) so a
typo in a YAML doesn't crash mid-run — the user sees the unsubstituted
``${typo}`` in the input field and can fix the macro.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping

log = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def substitute(text: str, variables: Mapping[str, Any]) -> str:
    """Replace every ``${name}`` in ``text`` with ``variables[name]``.

    Unknown names are kept verbatim. Values are converted to ``str``;
    callers should not stuff bytes / arbitrary objects into the dict.
    """
    if not text or "${" not in text:
        return text  # fast path

    def _sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in variables:
            log.debug("unknown variable ${%s}; leaving as-is", name)
            return m.group(0)
        return str(variables[name])

    return _VAR_PATTERN.sub(_sub, text)


def referenced_names(text: str) -> set[str]:
    """Return the set of variable names referenced in ``text``."""
    if not text or "${" not in text:
        return set()
    return {m.group(1) for m in _VAR_PATTERN.finditer(text)}
