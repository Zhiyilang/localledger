"""LocalLedger - an offline invoice & receipt organizer for freelancers."""
from .core import (Receipt, parse_text, parse_file, load, categorize,
                   summarize, write_csv, html_report, accountant_questions,
                   CURRENCY_SYMBOLS, CATEGORY_RULES)
from .llm import LocalModel, get_model

__version__ = "1.0.0"
__all__ = ["Receipt", "parse_text", "parse_file", "load", "categorize",
           "summarize", "write_csv", "html_report", "accountant_questions",
           "CURRENCY_SYMBOLS", "CATEGORY_RULES", "LocalModel", "get_model",
           "__version__"]
