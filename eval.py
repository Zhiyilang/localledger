"""LocalLedger self-test. Run: python eval.py  (no network, no deps)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from localledger.core import (parse_text, parse_file, categorize, summarize,
                              write_csv, html_report, accountant_questions)
from localledger.llm import LocalModel

PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS  %s" % name)
    else:
        FAIL += 1
        print("  FAIL  %s" % name)


EX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "receipts.txt")
receipts = parse_file(EX)

print("Parsing")
check("nine documents parsed", len(receipts) == 9)
check("first vendor is Adobe block", receipts[0].vendor == "ADOBE SYSTEMS INCORPORATED")
check("invoice number is not mistaken for a vendor",
      all("#" not in r.vendor for r in receipts))
check("Adobe date normalised to ISO", receipts[0].date == "2026-07-03")
check("Adobe amount", abs(receipts[0].amount - 22.99) < 1e-9)
check("Adobe currency USD", receipts[0].currency == "USD")
check("Uber fare parsed", abs(receipts[1].amount - 18.40) < 1e-9)
check("EUR symbol mapped", any(r.currency == "EUR" and abs(r.amount - 210.50) < 1e-9
                               for r in receipts))
check("GBP symbol mapped", any(r.currency == "GBP" and abs(r.amount - 14.99) < 1e-9
                               for r in receipts))
check("day-first date parsed", any(r.date == "2026-07-21" for r in receipts))
check("evidence trail present", len(receipts[0].evidence) >= 3)
check("evidence cites source line", receipts[0].evidence[0].startswith(EX))

print("Categorising")
check("Adobe -> Software", receipts[0].category == "Software")
check("Uber -> Travel", receipts[1].category == "Travel")
check("Starbucks -> Meals", receipts[2].category == "Meals")
check("Amazon paper/toner -> Office", receipts[4].category == "Office")
check("Google Ads -> Marketing", receipts[6].category == "Marketing")
check("Bookshop course book -> Education", receipts[8].category == "Education")
check("mystery vendor -> Uncategorized", receipts[7].category == "Uncategorized")
check("keyword helper is case-insensitive", categorize("LAPTOP purchase") == "Hardware")

print("Dates")
check("dd/mm/yyyy normalises", parse_text("X\nDate: 25/12/2026\nTotal: $1.00")[0].date
      == "2026-12-25")
check("month-first only value normalises",
      parse_text("X\nDate: 12/25/2026\nTotal: $1.00")[0].date == "2026-12-25")
check("ISO date accepted",
      parse_text("X\nDate: 2026-02-09\nTotal: $1.00")[0].date == "2026-02-09")

print("Summarising (offline engine)")
s = summarize(receipts, model=None)
check("count", s["count"] == 9)
check("USD total", abs(s["totals"]["USD"] - 224.33) < 1e-9)
check("EUR total", abs(s["totals"]["EUR"] - 210.50) < 1e-9)
check("GBP total", abs(s["totals"]["GBP"] - 14.99) < 1e-9)
check("primary currency is USD", s["primary_currency"] == "USD")
check("Software breakdown in USD", abs(s["by_category"]["Software"]["USD"] - 37.99) < 1e-9)
check("top category is Marketing", s["ranked"][0][0] == "Marketing")
check("uncategorised counted", s["uncategorized"] == 1)
check("engine label is offline", s["engine"] == "deterministic-offline")
check("offline narrative mentions on-device", "on this device" in s["narrative"])

print("Model fallback")
dead = LocalModel(url="http://127.0.0.1:59999")
check("unreachable model reports unavailable", dead.available() is False)
s2 = summarize(receipts, model=dead)
check("falls back when model is unreachable", s2["engine"] == "deterministic-offline")
check("fallback narrative non-empty", len(s2["narrative"]) > 20)

print("Questions and reports")
qs = accountant_questions(receipts)
check("at least three accountant questions", len(qs) >= 3)
check("meals question raised", any("Meals" in q for q in qs))
check("multi-currency question raised", any("exchange rate" in q for q in qs))

tmp = tempfile.mkdtemp()
csv_path = os.path.join(tmp, "ledger.csv")
write_csv(receipts, csv_path)
rows = open(csv_path, encoding="utf-8").read().strip().splitlines()
check("csv header written", rows[0].startswith("date,vendor,amount"))
check("csv has one row per document", len(rows) == 10)

html_path = os.path.join(tmp, "review.html")
html_report(s, receipts, html_path, title="Q3 2026 review")
doc = open(html_path, encoding="utf-8").read()
check("html shows title", "Q3 2026 review" in doc)
check("html shows a vendor", "ADOBE SYSTEMS INCORPORATED" in doc)
check("html shows the USD total", "224.33" in doc)
check("html has no unsubstituted placeholders", "__" not in doc)

# guard: template marker for both files
check("html engine badge present", "deterministic-offline" in doc)

print()
print("RESULT: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
