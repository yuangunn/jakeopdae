"""SQLite store for macro run history.

Two tables:

  ``runs``       — one row per ``Runner.run()`` invocation
  ``run_steps``  — one row per step execution (multiple per run)

The store doubles as a :class:`RunObserver` so the runner can be wired
up directly:

.. code-block:: python

    from keymacro.history import HistoryStore, default_history_path
    store = HistoryStore(default_history_path())
    observer = store.observer()
    Runner(macro, ..., observer=observer).run()

Reads (``list_recent_runs``, ``stats_for_macro``) power the GUI's run
history dashboard. Writes are pessimistic — every event commits — so a
crash mid-run leaves a partial-but-readable record.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    macro_name      TEXT NOT NULL,
    started_at      REAL NOT NULL,
    ended_at        REAL,
    completed       INTEGER,
    aborted_at      TEXT,
    duration_s      REAL,
    num_steps       INTEGER NOT NULL DEFAULT 0,
    num_succeeded   INTEGER NOT NULL DEFAULT 0,
    num_failed      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_runs_macro_started
    ON runs(macro_name, started_at DESC);

CREATE TABLE IF NOT EXISTS run_steps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL,
    step_id       TEXT NOT NULL,
    started_at    REAL NOT NULL,
    ended_at      REAL,
    success       INTEGER,
    error         TEXT,
    duration_s    REAL,
    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_run_steps_run ON run_steps(run_id);
"""


def default_history_path() -> Path:
    """``%LOCALAPPDATA%\\keymacro\\history.db`` on Windows; XDG path on POSIX."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(
            Path.home() / ".local" / "share"
        )
    p = Path(base) / "keymacro" / "history.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


class HistoryStore:
    """SQLite-backed run history. Thread-safe enough for our usage —
    pysqlite uses a single connection with ``check_same_thread=False``,
    and writes are short."""

    def __init__(self, path: Path | str = ":memory:") -> None:
        self.path = path
        self._conn = sqlite3.connect(
            str(path), isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # --- observer factory ---------------------------------------------

    def observer(self) -> "HistoryObserver":
        return HistoryObserver(self)

    # --- write API used by HistoryObserver -----------------------------

    def begin_run(self, macro_name: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO runs(macro_name, started_at) VALUES (?, ?)",
            (macro_name, time.time()),
        )
        return int(cur.lastrowid)

    def begin_step(self, run_id: int, step_id: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO run_steps(run_id, step_id, started_at) VALUES (?, ?, ?)",
            (run_id, step_id, time.time()),
        )
        return int(cur.lastrowid)

    def end_step(
        self,
        row_id: int,
        *,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        now = time.time()
        self._conn.execute(
            "UPDATE run_steps SET ended_at = ?, success = ?, error = ?, "
            "duration_s = ? - started_at WHERE id = ?",
            (now, 1 if success else 0, error, now, row_id),
        )

    def end_run(
        self,
        run_id: int,
        *,
        completed: bool,
        aborted_at: Optional[str] = None,
    ) -> None:
        now = time.time()
        # Aggregate counts in one go from run_steps for this run.
        row = self._conn.execute(
            "SELECT COUNT(*) AS n, "
            "  SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS ok, "
            "  SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS bad "
            "FROM run_steps WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        n = int(row["n"] or 0)
        ok = int(row["ok"] or 0)
        bad = int(row["bad"] or 0)
        self._conn.execute(
            "UPDATE runs SET ended_at = ?, completed = ?, aborted_at = ?, "
            "duration_s = ? - started_at, num_steps = ?, num_succeeded = ?, "
            "num_failed = ? WHERE id = ?",
            (now, 1 if completed else 0, aborted_at, now, n, ok, bad, run_id),
        )

    # --- read API used by the GUI dashboard ----------------------------

    def list_recent_runs(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def stats_for_macro(self, macro_name: str) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) AS total, "
            "  SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed, "
            "  AVG(duration_s) AS avg_duration_s, "
            "  MAX(started_at) AS last_run_at "
            "FROM runs WHERE macro_name = ?",
            (macro_name,),
        ).fetchone()
        total = int(row["total"] or 0)
        completed = int(row["completed"] or 0)
        return {
            "total": total,
            "completed": completed,
            "success_rate": (completed / total) if total else 0.0,
            "avg_duration_s": row["avg_duration_s"] or 0.0,
            "last_run_at": row["last_run_at"],
        }

    def steps_for_run(self, run_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM run_steps WHERE run_id = ? ORDER BY started_at",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# --- RunObserver implementation -------------------------------------------


@dataclass
class HistoryObserver:
    """:class:`RunObserver` that mirrors every callback into the store."""

    store: HistoryStore
    _run_id: Optional[int] = None
    _step_row_ids: dict[str, int] = field(default_factory=dict)

    # --- protocol callbacks -------------------------------------------

    def on_run_start(self, macro_name: str) -> None:
        try:
            self._run_id = self.store.begin_run(macro_name)
        except Exception:
            log.exception("history begin_run failed")
            self._run_id = None

    def on_step_start(self, step_id: str, attempt: int, iteration: int) -> None:
        if self._run_id is None:
            return
        # Only record the first attempt's row to avoid bloating the
        # table — retries get aggregated under the same step row.
        if step_id in self._step_row_ids:
            return
        try:
            row = self.store.begin_step(self._run_id, step_id)
            self._step_row_ids[step_id] = row
        except Exception:
            log.exception("history begin_step failed")

    def on_match_attempt(self, *_a, **_kw) -> None: ...

    def on_step_end(self, step_id: str, success: bool, match, error) -> None:
        if self._run_id is None:
            return
        row = self._step_row_ids.pop(step_id, None)
        if row is None:
            return
        try:
            self.store.end_step(row, success=success, error=error)
        except Exception:
            log.exception("history end_step failed")

    def on_failure_capture(self, *_a, **_kw) -> None: ...

    def on_run_end(self, completed: bool, aborted_at) -> None:
        if self._run_id is None:
            return
        try:
            self.store.end_run(
                self._run_id, completed=completed,
                aborted_at=aborted_at,
            )
        except Exception:
            log.exception("history end_run failed")
        self._run_id = None
        self._step_row_ids.clear()
