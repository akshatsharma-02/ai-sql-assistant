"""
Layer 2 of the safety design: validate SQL text *before* it reaches the database.

The LLM is told to write only SELECT queries (layer 1), but a prompt is a
request, not a guarantee. This module checks the SQL itself and rejects
anything that is not a single read-only query. Layer 3 (in db.py) enforces
the same rule inside SQLite, so even a query that slips past this check
still cannot change data.
"""

import re

# Statements that could change data, change the database file, or reach
# outside it. ATTACH could open other files; PRAGMA can change settings.
FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "replace", "upsert", "merge",
    "drop", "alter", "create", "truncate", "reindex", "vacuum",
    "attach", "detach", "pragma", "analyze",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)


class UnsafeQueryError(ValueError):
    """Raised when SQL is not a single, read-only SELECT query."""


def clean_llm_output(text: str) -> str:
    """Strip the formatting LLMs often wrap around SQL (```sql fences, 'SQL:' labels)."""
    sql = text.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", sql, re.DOTALL | re.IGNORECASE)
    if fence:
        sql = fence.group(1)
    sql = re.sub(r"^\s*sql\s*:\s*", "", sql, flags=re.IGNORECASE)
    return sql.strip()


def _strip_literals_and_comments(sql: str) -> str:
    """
    Remove string literals, quoted names, and comments so keyword checks only
    look at real SQL. Without this, a harmless filter like
    WHERE ProductName = 'Drop Cookies' would be wrongly blocked, and a
    dangerous word hidden in a comment could confuse the checks.
    """
    out, i, n = [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"', "`", "["):
            close = {"'": "'", '"': '"', "`": "`", "[": "]"}[ch]
            j = i + 1
            while j < n:
                if sql[j] == close:
                    # Doubled quotes ('') are an escaped quote inside a literal.
                    if close in "'\"" and j + 1 < n and sql[j + 1] == close:
                        j += 2
                        continue
                    break
                j += 1
            out.append(" ")  # replace the whole literal with a space
            i = j + 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def validate_select(sql: str) -> str:
    """
    Return the query (trailing semicolon removed) if it is a single read-only
    SELECT; otherwise raise UnsafeQueryError explaining why.
    """
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise UnsafeQueryError("The query is empty.")

    bare = _strip_literals_and_comments(sql)

    # One statement only: "SELECT 1; DROP TABLE Customer" is two statements.
    if ";" in bare:
        raise UnsafeQueryError("Only one SQL statement is allowed.")

    first_word = bare.strip().split(None, 1)[0].lower() if bare.strip() else ""
    if first_word not in ("select", "with"):
        raise UnsafeQueryError("Only SELECT queries are allowed.")

    match = _FORBIDDEN_RE.search(bare)
    if match:
        raise UnsafeQueryError(f"'{match.group(1).upper()}' is not allowed in a read-only query.")

    return sql
