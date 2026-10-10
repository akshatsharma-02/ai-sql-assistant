# 🧠 AI SQL Assistant

Ask questions about a sales database in plain English. An LLM writes the SQL, the app checks that it is safe, runs it on a read-only database, and shows the answer as a table and chart. If the generated SQL fails, the model sees the error and corrects itself.

**🔗 Live demo:** _add your Streamlit Cloud link here_

<!-- Add a screenshot: screenshots/demo.png -->

---

## Why this project

Business users have questions about their data but can't write SQL. Text-to-SQL with an LLM solves that, but letting a model write queries against a real database raises two problems this project tackles directly:

1. **Safety:** a model can be manipulated, or simply mistaken, into writing a query that deletes or changes data.
2. **Accuracy:** a query that runs without errors can still answer the wrong question, so "it worked" is not evidence that it's correct.

## How it works

```
Question ──▶ Prompt (live schema + business rules) ──▶ LLM (gpt-oss-120b on Groq)
                                                            │
                                                            ▼
                                       Validate SQL (single read-only SELECT?)
                                            │                     │
                                          fails                 passes
                                            │                     ▼
                       error sent back ◀────┤          Run on read-only SQLite
                       for one retry        │          (authorizer, 1,000-row cap,
                                            └────────── 10-second timeout)
                                                                  │
                                                                  ▼
                                                        Table + automatic chart
```

- **Live schema:** the table and column list in the prompt is read from the database at startup, so it can never drift out of date.
- **Business rules in the prompt:** the model is told how revenue is calculated, how dates are stored, and how tables join. These are facts the schema alone doesn't express.
- **Self-correction:** if a query fails validation or execution (for example, a misspelled column), the error message goes back to the model for one corrected attempt.
- **Knows its limits:** if a question can't be answered from the data (such as shipping costs, which aren't stored), the model returns `CANNOT_ANSWER` instead of inventing a query.

## Safety: three independent layers

| Layer | Where | What it does |
|---|---|---|
| 1. Prompt | `llm.py` | Instructs the model to write only `SELECT` queries. Helpful, but a request rather than a guarantee. |
| 2. Validator | `guard.py` | Rejects multiple statements, non-`SELECT` queries, and keywords like `DROP`, `ATTACH`, `PRAGMA`. String literals and comments are stripped first, so `WHERE name = 'Drop Cookies'` isn't wrongly blocked. |
| 3. Database | `db.py` | Opens SQLite in read-only mode and attaches an **authorizer** that denies every action except reading. This holds even if layers 1 and 2 are bypassed. |

On top of that, user-chosen values in built-in reports use **parameterized queries** (protection against SQL injection), and every query is capped at 1,000 rows and 10 seconds.

The test suite proves each layer works, including sending `DELETE` and `DROP` directly to the database with the validator bypassed:

```bash
python -m unittest discover tests -v
```

## Evaluation

`eval/questions.json` contains 22 questions with hand-written correct SQL across four levels: easy, medium (joins and grouping), hard (multi-table joins, dates, subqueries), and unanswerable.

The metric is **execution accuracy**: the generated query and the correct query are both run, and their *results* are compared. Comparing SQL text would undercount, since many different queries are equally correct.

```bash
python eval/run_eval.py
```

**Results:** _run the evaluation and paste the summary from `eval/results.md` here._

## Data

A normalized sales database (SQLite, 6 tables, about 622,000 order lines from July 2012 to February 2016): regions, countries, customers, product categories, products, and orders. The data originates from a university database course exercise.

## Run it locally

```bash
git clone https://github.com/akshatsharma-02/ai-sql-assistant.git
cd ai-sql-assistant
pip install -r requirements.txt
cp .env.example .env          # then add your free Groq API key from console.groq.com
streamlit run app.py
```

The **Built-in reports** and **Write SQL** tabs work without an API key.

## Project structure

```
ai-sql-assistant/
├── app.py                  # Streamlit interface
├── sql_assistant/
│   ├── llm.py              # prompt, LLM call, self-correction loop
│   ├── guard.py            # SQL validation (safety layer 2)
│   ├── db.py               # read-only connection, authorizer, limits (layer 3)
│   └── reports.py          # hand-written, parameterized business reports
├── eval/
│   ├── questions.json      # 22 test questions with correct SQL
│   └── run_eval.py         # execution-accuracy evaluation
├── tests/test_safety.py    # proves the safety layers hold
└── data/sales.db           # the SQLite database
```

## Limitations and next steps

- **Single database, fixed schema.** The prompt approach works for a schema this size; for databases with hundreds of tables, the next step would be retrieving only the relevant tables for each question.
- **Execution accuracy has a known blind spot:** a wrong query can occasionally return the same result as the right one by coincidence. A larger, more varied question set reduces this risk.
- **One correction attempt.** More retries raise cost and latency for small gains; this is a deliberate trade-off.
- **SQLite only.** For a production database, the same three-layer design would use a database user with read-only permissions in place of the authorizer.

## Tech stack

Python · Streamlit · Groq API (OpenAI gpt-oss-120b; model is configurable) · SQLite · pandas
