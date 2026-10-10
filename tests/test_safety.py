"""
Tests for the safety layers. Run with:  python -m unittest discover tests

Each test answers one question an interviewer might ask:
"What stops the AI (or a user) from deleting your data?"
"""

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sql_assistant.db import DEFAULT_DB_PATH, connect_readonly, run_select  # noqa: E402
from sql_assistant.guard import UnsafeQueryError, clean_llm_output, validate_select  # noqa: E402
from sql_assistant.reports import REPORTS  # noqa: E402


class GuardAllowsReadQueries(unittest.TestCase):
    def test_simple_select(self):
        self.assertEqual(validate_select("SELECT * FROM Customer;"), "SELECT * FROM Customer")

    def test_cte(self):
        validate_select("WITH t AS (SELECT 1 AS x) SELECT x FROM t")

    def test_forbidden_word_inside_string_is_fine(self):
        # 'Drop' and 'Update' here are data, not commands.
        validate_select("SELECT * FROM Product WHERE ProductName IN ('Drop Cookies', 'Update Tea')")

    def test_strips_markdown_from_llm(self):
        raw = "```sql\nSELECT 1;\n```"
        self.assertEqual(validate_select(clean_llm_output(raw)), "SELECT 1")


class GuardBlocksUnsafeQueries(unittest.TestCase):
    unsafe = [
        "DELETE FROM Customer",
        "DROP TABLE Customer",
        "UPDATE Product SET ProductUnitPrice = 0",
        "INSERT INTO Region VALUES (99, 'X')",
        "SELECT 1; DROP TABLE Customer",                    # stacked statements
        "SELECT 1 /* hide */ ; DELETE FROM Customer",       # semicolon after a comment
        "ATTACH DATABASE 'other.db' AS o",                   # reach another file
        "PRAGMA writable_schema = 1",
        "WITH x AS (SELECT 1) DELETE FROM Customer",         # write disguised as a CTE
        "",
    ]

    def test_all_blocked(self):
        for sql in self.unsafe:
            with self.subTest(sql=sql), self.assertRaises(UnsafeQueryError):
                validate_select(sql)


class DatabaseLayerBlocksWritesEvenWithoutGuard(unittest.TestCase):
    """Skip guard.py entirely and send dangerous SQL straight to SQLite."""

    @classmethod
    def setUpClass(cls):
        cls.conn = connect_readonly(DEFAULT_DB_PATH)

    def test_writes_rejected_by_sqlite(self):
        for sql in ["DELETE FROM Customer", "DROP TABLE Region",
                    "UPDATE Product SET ProductUnitPrice = 0", "PRAGMA writable_schema = 1"]:
            with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                self.conn.execute(sql)

    def test_data_unchanged(self):
        count = self.conn.execute("SELECT COUNT(*) FROM Customer").fetchone()[0]
        self.assertEqual(count, 91)


class ParameterizedQueriesResistInjection(unittest.TestCase):
    def test_malicious_customer_name_is_treated_as_data(self):
        conn = connect_readonly(DEFAULT_DB_PATH)
        sql = REPORTS["Customer summary"]["sql"]
        df, _ = run_select(conn, sql, ("x' OR '1'='1",))
        self.assertTrue(df.empty)  # no customer has that name; nothing leaks


class ResourceLimits(unittest.TestCase):
    def test_row_cap(self):
        conn = connect_readonly(DEFAULT_DB_PATH)
        df, truncated = run_select(conn, "SELECT * FROM OrderDetail", max_rows=50)
        self.assertEqual(len(df), 50)
        self.assertTrue(truncated)

    def test_runaway_query_times_out(self):
        conn = connect_readonly(DEFAULT_DB_PATH)
        # A cross join of 600k x 600k rows would run for hours.
        with self.assertRaises(TimeoutError):
            run_select(conn, "SELECT COUNT(*) FROM OrderDetail a, OrderDetail b", timeout_s=1)


if __name__ == "__main__":
    unittest.main()
