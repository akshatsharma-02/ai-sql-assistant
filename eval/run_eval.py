"""
Measure how accurate the assistant is.

Metric: execution accuracy. For each question we run both the model's SQL and
a hand-written correct ("gold") query, then compare the *results*, not the SQL
text. Two different-looking queries can both be correct, so comparing text
would undercount. Column names and order are ignored, numbers are compared
after rounding, and row order only matters when the question asks for a ranking.

Usage (needs GROQ_API_KEY in your environment or .env):
    python eval/run_eval.py
    python eval/run_eval.py --check-gold   # only verify the gold queries run (no API key)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sql_assistant.db import connect_readonly, get_schema_text, run_select  # noqa: E402
from sql_assistant.llm import CANNOT_ANSWER, DEFAULT_MODEL, answer_question  # noqa: E402


def normalize(df, ordered: bool):
    """Turn a result table into a comparable form: rounded values, optional sorting."""
    rows = []
    for row in df.itertuples(index=False):
        rows.append(tuple(round(v, 2) if isinstance(v, float) else v for v in row))
    return rows if ordered else sorted(rows, key=repr)


def results_match(pred_df, gold_df, ordered: bool) -> bool:
    if pred_df is None:
        return False
    # Allow extra columns in the prediction (e.g. a model that also returns a count)
    # as long as every gold column's values appear: compare on the gold column count
    # when shapes differ only by extra columns.
    if pred_df.shape[1] > gold_df.shape[1]:
        for start in range(pred_df.shape[1] - gold_df.shape[1] + 1):
            sub = pred_df.iloc[:, start:start + gold_df.shape[1]]
            if normalize(sub, ordered) == normalize(gold_df, ordered):
                return True
    return normalize(pred_df, ordered) == normalize(gold_df, ordered)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-gold", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    questions = json.loads((ROOT / "eval" / "questions.json").read_text())
    conn = connect_readonly()

    if args.check_gold:
        for q in questions:
            if q["gold_sql"] != CANNOT_ANSWER:
                df, _ = run_select(conn, q["gold_sql"])
                print(f"#{q['id']:>2} ok  rows={len(df)}")
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    from groq import Groq
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    schema = get_schema_text(conn)

    lines, by_level = [], {}
    for q in questions:
        time.sleep(1)  # stay under free-tier rate limits
        res = answer_question(client, conn, q["question"], schema, model=args.model)
        if q["gold_sql"] == CANNOT_ANSWER:
            correct = res.attempts[:1] == [CANNOT_ANSWER] or "can't be answered" in res.error
        else:
            gold_df, _ = run_select(conn, q["gold_sql"])
            correct = results_match(res.dataframe, gold_df, q.get("ordered", False))
        retried = len(res.attempts) > 1
        by_level.setdefault(q["level"], []).append(correct)
        mark = "PASS" if correct else "FAIL"
        print(f"#{q['id']:>2} [{q['level']:<12}] {mark}{' (after retry)' if retried and correct else ''}  {q['question']}")
        lines.append(f"| {q['id']} | {q['level']} | {mark} | {'yes' if retried else ''} | "
                     f"{q['question']} | `{(res.sql or res.error).replace('|', '/').replace(chr(10), ' ')}` |")

    total = sum(sum(v) for v in by_level.values())
    n = sum(len(v) for v in by_level.values())
    summary = [f"**Model:** {args.model}  ", f"**Execution accuracy:** {total}/{n} ({total / n:.0%})", ""]
    summary += [f"- {lvl}: {sum(v)}/{len(v)}" for lvl, v in by_level.items()]
    report = "\n".join(["# Evaluation results", ""] + summary + ["",
                       "| # | Level | Result | Retried | Question | SQL or error |",
                       "|---|---|---|---|---|---|"] + lines) + "\n"
    (ROOT / "eval" / "results.md").write_text(report)
    print("\n" + "\n".join(summary))
    print("Saved eval/results.md")


if __name__ == "__main__":
    main()
