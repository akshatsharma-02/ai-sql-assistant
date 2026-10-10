"""
Database access, with layer 3 of the safety design built in.

Two database-level protections apply to every connection:
  1. The file is opened in read-only mode (mode=ro), so SQLite itself refuses writes.
  2. An "authorizer" callback approves or denies every action SQLite is about
     to take. Only reading tables, running SELECTs, and calling functions are
     allowed. This works even if a malicious query gets past guard.py.
"""

import sqlite3
import time
from pathlib import Path

import pandas as pd

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sales.db"

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,     # run a SELECT
    sqlite3.SQLITE_READ,       # read a column of a table
    sqlite3.SQLITE_FUNCTION,   # call functions like SUM(), strftime()
}
# WITH RECURSIVE support exists only in newer Python builds.
if hasattr(sqlite3, "SQLITE_RECURSIVE"):
    _ALLOWED_ACTIONS.add(sqlite3.SQLITE_RECURSIVE)


def _read_only_authorizer(action, arg1, arg2, db_name, trigger):
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def connect_readonly(db_path=DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the database read-only, with the authorizer attached."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    conn.set_authorizer(_read_only_authorizer)
    return conn


def get_schema_text(conn: sqlite3.Connection) -> str:
    """
    Describe every table and its columns, read live from the database.
    The LLM receives this text, so the prompt always matches the real schema
    instead of a hand-typed copy that can drift out of date.
    """
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    lines = []
    for table in tables:
        cols = _columns(conn, table)
        lines.append(f"- {table}({', '.join(cols)})")
    return "\n".join(lines)


def _columns(conn: sqlite3.Connection, table: str) -> list:
    # Read column names with a zero-row SELECT. PRAGMA is blocked by the
    # authorizer, and this keeps schema reading inside the same rules.
    cur = conn.execute(f"SELECT * FROM [{table}] LIMIT 0")
    return [d[0] for d in cur.description]


def run_select(conn: sqlite3.Connection, sql: str, params=(), max_rows: int = 1000,
               timeout_s: float = 10.0):
    """
    Run a read-only query and return (DataFrame, truncated_flag).

    max_rows caps how much is returned so a broad query can't flood the page.
    timeout_s stops runaway queries (for example, an accidental cross join of
    a 600,000-row table) instead of freezing the app.
    """
    deadline = time.monotonic() + timeout_s
    # SQLite calls this every 10,000 steps; returning 1 aborts the query.
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchmany(max_rows + 1)
        columns = [d[0] for d in cur.description] if cur.description else []
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise TimeoutError(f"Query took longer than {timeout_s:.0f} seconds and was stopped.") from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)

    truncated = len(rows) > max_rows
    return pd.DataFrame(rows[:max_rows], columns=columns), truncated
