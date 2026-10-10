"""
Load settings from the project's .env file as soon as the package is imported,
so values like GROQ_API_KEY and GROQ_MODEL are available to every module,
regardless of which file (app.py, eval/run_eval.py) starts the program.
"""

from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv not installed: rely on real environment variables
    pass