"""
Natural language to SQL with an LLM (Llama 3.3 on Groq by default).

Flow for one question:
  1. Build a prompt containing the live schema, business rules, and the question.
  2. Ask the model for SQL (layer 1 of safety: the prompt asks for SELECT only).
  3. Clean and validate the SQL (layer 2, guard.py).
  4. Run it on the read-only connection (layer 3, db.py).
  5. If validation or execution fails, send the error back to the model once
     and let it correct its own query ("self-correction").
"""

import os
from dataclasses import dataclass, field

from .db import run_select
from .guard import UnsafeQueryError, clean_llm_output, validate_select

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
CANNOT_ANSWER = "CANNOT_ANSWER"

# Business knowledge the schema alone can't express. Without these rules the
# model has to guess what "sales" means or how dates are stored.
SYSTEM_PROMPT = """You write SQLite queries for a sales database.

Rules:
- Return ONE SQLite SELECT query and nothing else: no explanation, no markdown.
- Use only the tables and columns listed in the schema.
- Revenue or sales amount = OrderDetail.QuantityOrdered * Product.ProductUnitPrice.
- OrderDate is text in 'YYYY-MM-DD' format; use strftime('%Y', OrderDate) or strftime('%Y-%m', OrderDate) for years and months. Data covers 2012-07 to 2016-02.
- A customer's full name is FirstName || ' ' || LastName.
- Join path: OrderDetail -> Customer -> Country -> Region, and OrderDetail -> Product -> ProductCategory.
- Round money values to 2 decimals with ROUND(..., 2).
- Add LIMIT 100 unless the question asks for a specific number of rows or a single value.
- If the question cannot be answered from this schema, return exactly: CANNOT_ANSWER"""


@dataclass
class AssistantResult:
    question: str
    sql: str = ""
    dataframe: object = None
    truncated: bool = False
    error: str = ""
    attempts: list = field(default_factory=list)  # every SQL tried, for transparency


def _build_messages(question: str, schema: str, previous_sql: str = "", error: str = ""):
    user = f"Schema:\n{schema}\n\nQuestion: {question}"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]
    if previous_sql:
        # Self-correction: show the model its own failed query and the exact error.
        messages.append({"role": "assistant", "content": previous_sql})
        messages.append({"role": "user", "content": f"That query failed with this error:\n{error}\n"
                                                    "Return a corrected SQLite SELECT query only."})
    return messages


def generate_sql(client, question: str, schema: str, model: str = DEFAULT_MODEL,
                 previous_sql: str = "", error: str = "") -> str:
    """One LLM call. temperature=0 makes answers as repeatable as possible."""
    response = client.chat.completions.create(
        model=model,
        messages=_build_messages(question, schema, previous_sql, error),
        temperature=0,
    )
    return clean_llm_output(response.choices[0].message.content or "")


def answer_question(client, conn, question: str, schema: str, model: str = DEFAULT_MODEL,
                    max_retries: int = 1, max_rows: int = 1000) -> AssistantResult:
    """Full pipeline: generate -> validate -> run, with one self-correction retry."""
    result = AssistantResult(question=question)
    previous_sql, error = "", ""

    for _ in range(max_retries + 1):
        sql = generate_sql(client, question, schema, model, previous_sql, error)
        result.attempts.append(sql)

        if sql.strip().upper() == CANNOT_ANSWER:
            result.error = "This question can't be answered from the sales database."
            return result

        try:
            safe_sql = validate_select(sql)
        except UnsafeQueryError as exc:
            previous_sql, error = sql, str(exc)
            continue

        try:
            df, truncated = run_select(conn, safe_sql, max_rows=max_rows)
        except TimeoutError as exc:
            result.sql, result.error = safe_sql, str(exc)  # retrying won't fix a slow query
            return result
        except Exception as exc:  # e.g. misspelled column -> let the model fix it
            previous_sql, error = safe_sql, str(exc)
            continue

        result.sql, result.dataframe, result.truncated = safe_sql, df, truncated
        return result

    result.sql = previous_sql
    result.error = f"Couldn't produce a working query: {error}"
    return result
