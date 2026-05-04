"""``setup_logging`` should write a per-run file under the chosen dir."""

from __future__ import annotations

import logging
from pathlib import Path

from keymacro.core.logger import setup_logging


def test_setup_logging_creates_log_file(tmp_path: Path):
    path = setup_logging(verbose=True, log_dir=tmp_path)
    assert path is not None
    assert path.exists()
    logging.getLogger("keymacro.test").info("hello world")
    # Force handler flush.
    for h in logging.getLogger().handlers:
        h.flush()
    contents = path.read_text(encoding="utf-8")
    assert "hello world" in contents


def test_setup_logging_replaces_handlers(tmp_path: Path):
    setup_logging(verbose=False, log_dir=tmp_path)
    first_handlers = list(logging.getLogger().handlers)
    setup_logging(verbose=False, log_dir=tmp_path)
    second_handlers = list(logging.getLogger().handlers)
    assert first_handlers != second_handlers
