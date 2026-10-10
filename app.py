"""
AI SQL Assistant: ask questions about a sales database in plain English.

Run locally:  streamlit run app.py
"""

import os

import pandas as pd
import streamlit as st

from sql_assistant.db import connect_readonly, get_schema_text, run_select
from sql_assistant.guard import UnsafeQueryError, validate_select
from sql_assistant.llm import DEFAULT_MODEL, answer_question
from sql_assistant.reports import CUSTOMER_NAMES_SQL, REPORTS

try:  # load a local .env file if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MAX_AI_QUESTIONS = int(os.getenv("MAX_AI_QUESTIONS", "25"))  # per session, protects your API quota
EXAMPLE_QUESTIONS = [
    "Which 5 products brought in the most revenue in 2015?",
    "How many customers are in each country?",
    "What was the monthly revenue trend in 2014?",
    "Which product category sells the most units in Western Europe?",
]

st.set_page_config(page_title="AI SQL Assistant", page_icon="🧠", layout="wide")


def get_api_key() -> str:
    """Read the key from Streamlit secrets (deployment) or environment (local). Never from code."""
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:  # no secrets file configured
        pass
    return os.getenv("GROQ_API_KEY", "")


@st.cache_resource
def get_conn():
    return connect_readonly()


@st.cache_resource
def get_client():
    key = get_api_key()
    if not key:
        return None
    from groq import Groq
    return Groq(api_key=key)


@st.cache_data
def get_schema() -> str:
    return get_schema_text(get_conn())


@st.cache_data
def get_customers() -> list:
    df, _ = run_select(get_conn(), CUSTOMER_NAMES_SQL)
    return df["Name"].tolist()


def show_result(df: pd.DataFrame, truncated: bool):
    """Table, plus an automatic chart when the result is a label + a number."""
    if df.empty:
        st.info("The query ran successfully but returned no rows.")
        return
    note = f"{len(df):,} rows" + (" (showing the first 1,000)" if truncated else "")
    st.caption(note)
    st.dataframe(df, hide_index=True)

    if df.shape[1] == 2 and pd.api.types.is_numeric_dtype(df.iloc[:, 1]) and 1 < len(df) <= 60:
        label = df.columns[0]
        chart_df = df.set_index(label)
        if "month" in label.lower() or "year" in label.lower():
            st.line_chart(chart_df)
        else:
            st.bar_chart(chart_df)


# ---------------- Sidebar ----------------
with st.sidebar:
    st.title("🧠 AI SQL Assistant")
    st.write("Ask questions about a sales database in plain English. "
             "The assistant writes the SQL, checks it is safe, runs it, and shows the result.")
    st.subheader("How it stays safe")
    st.markdown(
        "1. The model is instructed to write only `SELECT` queries.\n"
        "2. Every query is validated: one statement, read-only keywords only.\n"
        "3. The database is opened read-only and SQLite itself blocks any write.\n"
        "4. Queries are capped at 1,000 rows and 10 seconds."
    )
    with st.expander("Database schema"):
        st.code(get_schema(), language="text")
    st.caption(f"Model: {DEFAULT_MODEL} via Groq")

# ---------------- Main ----------------
st.title("Ask your sales data anything")
tab_ai, tab_reports, tab_sql = st.tabs(["💬 Ask in English", "📊 Built-in reports", "🛠️ Write SQL"])

with tab_ai:
    client = get_client()
    if client is None:
        st.warning("Set GROQ_API_KEY (in a .env file or Streamlit secrets) to enable AI questions. "
                   "The other two tabs work without it.")
    else:
        used = st.session_state.setdefault("ai_questions_used", 0)
        st.caption("Try: " + " · ".join(f"*{q}*" for q in EXAMPLE_QUESTIONS))
        with st.form("ask"):
            question = st.text_input("Your question", placeholder=EXAMPLE_QUESTIONS[0])
            submitted = st.form_submit_button("Ask")

        if submitted:
            if not question.strip():
                st.warning("Type a question first.")
            elif used >= MAX_AI_QUESTIONS:
                st.error(f"Question limit for this session reached ({MAX_AI_QUESTIONS}).")
            else:
                st.session_state.ai_questions_used += 1
                with st.spinner("Writing and running SQL..."):
                    try:
                        result = answer_question(client, get_conn(), question, get_schema())
                    except Exception as exc:  # network or API problems
                        st.error(f"Couldn't reach the AI service: {exc}")
                        st.stop()

                if result.sql:
                    st.markdown("**Generated SQL**")
                    st.code(result.sql, language="sql")
                if len(result.attempts) > 1 and not result.error:
                    with st.expander("The first attempt failed; the model corrected itself"):
                        for i, attempt in enumerate(result.attempts, 1):
                            st.markdown(f"Attempt {i}")
                            st.code(attempt, language="sql")
                if result.error:
                    st.error(result.error)
                else:
                    show_result(result.dataframe, result.truncated)

with tab_reports:
    choice = st.selectbox("Report", list(REPORTS))
    report = REPORTS[choice]
    st.caption(report["description"])
    params = ()
    if report["needs_customer"]:
        params = (st.selectbox("Customer", get_customers()),)
    if st.button("Run report"):
        with st.expander("SQL used"):
            st.code(report["sql"].strip(), language="sql")
        df, truncated = run_select(get_conn(), report["sql"], params)
        show_result(df, truncated)

with tab_sql:
    sql = st.text_area("Write a SELECT query", value="SELECT * FROM Customer LIMIT 10", height=150)
    if st.button("Run query"):
        try:
            df, truncated = run_select(get_conn(), validate_select(sql))
            show_result(df, truncated)
        except UnsafeQueryError as exc:
            st.error(f"Blocked: {exc}")
        except Exception as exc:
            st.error(f"Query error: {exc}")
