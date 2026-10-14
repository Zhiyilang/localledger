"""LocalLedger - offline invoice & receipt organizer for freelancers.

Pure standard library. Parses receipts/invoices from plain text blocks,
categorises them, and produces accounting-ready exports plus a quarterly
review written in plain language.

An open-weight local model (Ollama, or any OpenAI-compatible server) is used
when one is reachable; otherwise a deterministic offline fallback runs, so the
tool works with zero setup and no data ever leaves the machine.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import re
from dataclasses import dataclass, field

__all__ = [
    "Receipt", "parse_text", "parse_file", "load", "categorize",
    "summarize", "write_csv", "html_report", "accountant_questions",
    "CURRENCY_SYMBOLS", "CATEGORY_RULES",
]

CURRENCY_SYMBOLS = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP",
                    "\u00a5": "CNY", "\u20b9": "INR"}

CATEGORY_RULES = [
    ("Software", ["adobe", "creative cloud", "subscription", "saas", "license",
                  "github", "figma", "notion", "aws", "hosting", "domain",
                  "dropbox", "jetbrains", "slack"]),
    ("Hardware", ["laptop", "monitor", "keyboard", "mouse", "ssd", "camera",
                  "headphone", "cable", "adapter", "charger", "ram"]),
    ("Travel", ["flight", "airline", "hotel", "train", "uber", "taxi", "lyft",
                "airbnb", "parking", "fuel", "petrol", "railway", "lufthansa"]),
    ("Meals", ["restaurant", "cafe", "coffee", "lunch", "dinner", "catering",
               "starbucks", "meal", "bakery"]),
    ("Office", ["stationery", "printer", "paper", "desk", "chair", "shelf",
                "ink", "toner"]),
    ("Marketing", ["ads", "advertis", "promo", "marketing", "seo", "campaign"]),
    ("Professional", ["accountant", "lawyer", "legal", "consult", "notary",
                      "insurance", "bank fee", "audit"]),
    ("Education", ["course", "book", "udemy", "training", "conference",
                   "ticket", "workshop"]),
]

_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_DMY = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_SYMCLS = "$\u20ac\u00a3\u00a5\u20b9"
_AMOUNT = re.compile(
    r"(total|amount|paid|price|fare|sum|charged)[^\d" + _SYMCLS + r"]{0,12}"
    r"([" + _SYMCLS + r"])?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.I)
_AMOUNT_ANY = re.compile(
    r"([" + _SYMCLS + r"])\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_META = re.compile(
    r"^\s*(invoice|receipt|order|ref|reference|no|id|date|total|subtotal|"
    r"amount|tax|vat|gst|due|paid|payment|thank|fare|sum|charged|"
    r"customer|client)\b", re.I)


@dataclass
class Receipt:
    vendor: str
    date: str
    amount: float
    currency: str
    category: str
    note: str = ""
    source: str = ""
    evidence: list = field(default_factory=list)


def _norm_date(text):
    """Normalise a date to ISO. Day-first (dd/mm/yyyy) is the default; a value
    that can only be month-first is accepted via the second attempt."""
    m = _DATE_ISO.search(text)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)),
                            int(m.group(3))).isoformat()
        except ValueError:
            pass
    m = _DATE_DMY.search(text)
    if m:
        a, b, y = (int(x) for x in m.groups())
        if y < 100:
            y += 2000
        for d, mo in ((a, b), (b, a)):
            try:
                return _dt.date(y, mo, d).isoformat()
            except ValueError:
                continue
    return ""


def categorize(text):
    """Deterministic keyword scoring. Returns a category name or 'Uncategorized'."""
    t = (text or "").lower()
    best, best_hits = "Uncategorized", 0
    for cat, kws in CATEGORY_RULES:
        hits = sum(1 for kw in kws if kw in t)
        if hits > best_hits:
            best, best_hits = cat, hits
    return best


def _parse_block(block, source, start_line):
    lines = [ln.rstrip() for ln in block.strip().splitlines() if ln.strip()]
    if not lines:
        return None
    evidence = []

    vendor = ""
    v_idx = -1
    for i, ln in enumerate(lines):
        if _META.match(ln) or "#" in ln or len(ln.strip()) < 2:
            continue
        vendor, v_idx = ln.strip(), i
        evidence.append("%s:%d vendor=%r" % (source, start_line + i, vendor))
        break
    if not vendor:
        vendor, v_idx = lines[0].strip(), 0

    date_iso = ""
    for i, ln in enumerate(lines):
        if ln.lower().startswith("date") or _DATE_ISO.search(ln) or _DATE_DMY.search(ln):
            date_iso = _norm_date(ln)
            if date_iso:
                evidence.append("%s:%d date=%s" % (source, start_line + i, date_iso))
                break

    amount, currency = None, ""
    for i, ln in enumerate(lines):
        m = _AMOUNT.search(ln)
        if m:
            sym = m.group(2)
            currency = CURRENCY_SYMBOLS.get(sym, "USD") if sym else "USD"
            amount = float(m.group(3).replace(",", ""))
            evidence.append("%s:%d amount=%s %.2f" % (source, start_line + i, currency, amount))
            break
    if amount is None:
        for i, ln in enumerate(lines):
            m = _AMOUNT_ANY.search(ln)
            if m:
                currency = CURRENCY_SYMBOLS.get(m.group(1), "USD")
                amount = float(m.group(2).replace(",", ""))
                evidence.append("%s:%d amount=%s %.2f" % (source, start_line + i, currency, amount))
                break
    if amount is None:
        return None

    desc = [ln.strip() for j, ln in enumerate(lines)
            if j != v_idx and not _META.match(ln) and "#" not in ln
            and len(ln.strip()) > 3]
    note = desc[0] if desc else ""

    category = categorize("%s %s %s" % (vendor, note, " ".join(desc)))
    evidence.append("category=%s (keyword rules)" % category)
    return Receipt(vendor=vendor, date=date_iso, amount=round(amount, 2),
                   currency=currency, category=category, note=note,
                   source=source, evidence=evidence)


def parse_text(text, source="<text>"):
    receipts = []
    line = 1
    for block in re.split(r"\n\s*\n", text or ""):
        n = block.count("\n") + 1
        r = _parse_block(block, source, line)
        if r is not None:
            receipts.append(r)
        line += n + 1
    return receipts


def parse_file(path):
    with open(path, encoding="utf-8-sig") as f:
        return parse_text(f.read(), source=path)


#: friendly alias
load = parse_file


def _fallback_narrative(receipts, totals, primary, primary_total, uncat):
    parts = ["LocalLedger read %d documents entirely on this device." % len(receipts)]
    if primary_total:
        parts.append("The bulk of your spending is in %s, totalling %.2f %s."
                     % (primary, primary_total, primary))
    others = ", ".join("%.2f %s" % (v, k)
                       for k, v in sorted(totals.items()) if k != primary)
    if others:
        parts.append("Other currencies: %s." % others)
    if uncat:
        parts.append("%d item(s) could not be categorised automatically and need "
                     "a quick manual tag." % uncat)
    parts.append("Nothing was uploaded, so client and banking details stayed private.")
    return " ".join(parts)


def _summary_prompt(receipts, totals, primary_total):
    lines = ["You are a bookkeeping assistant. Write four short sentences in plain "
             "English summarising this quarter for a freelancer."]
    for r in receipts:
        lines.append("- %s | %s | %.2f %s | %s" % (r.date or "?", r.vendor,
                                                   r.amount, r.currency, r.category))
    lines.append("Totals: %s" % ", ".join("%.2f %s" % (v, k) for k, v in sorted(totals.items())))
    lines.append("Do not invent figures. Be concise.")
    return "\n".join(lines)


def summarize(receipts, model=None):
    totals, breakdown = {}, {}
    for r in receipts:
        totals[r.currency] = round(totals.get(r.currency, 0.0) + r.amount, 2)
        bucket = breakdown.setdefault(r.category, {})
        bucket[r.currency] = round(bucket.get(r.currency, 0.0) + r.amount, 2)
    primary = max(totals.items(), key=lambda kv: (kv[1], kv[0]))[0] if totals else "USD"
    primary_total = totals.get(primary, 0.0)
    ranked = sorted(((c, d.get(primary, 0.0)) for c, d in breakdown.items()),
                    key=lambda kv: (-kv[1], kv[0]))
    uncat = sum(1 for r in receipts if r.category == "Uncategorized")

    engine = "deterministic-offline"
    narrative = None
    if model is not None and model.available():
        narrative = model.summarize(_summary_prompt(receipts, totals, primary_total))
        if narrative:
            engine = "local-open-weight-model"
    if not narrative:
        narrative = _fallback_narrative(receipts, totals, primary, primary_total, uncat)

    return {
        "count": len(receipts),
        "totals": totals,
        "primary_currency": primary,
        "primary_total": round(primary_total, 2),
        "by_category": breakdown,
        "ranked": [(c, round(v, 2)) for c, v in ranked],
        "uncategorized": uncat,
        "engine": engine,
        "narrative": narrative,
    }


def accountant_questions(receipts):
    qs = []
    meals = round(sum(r.amount for r in receipts if r.category == "Meals"), 2)
    if meals:
        qs.append("Meals & entertainment total %.2f - confirm the deductible "
                  "percentage in your jurisdiction." % meals)
    uncat = [r for r in receipts if r.category == "Uncategorized"]
    if uncat:
        names = ", ".join(sorted({r.vendor for r in uncat}))[:70]
        qs.append("%d uncategorised item(s) (%s) - can they be assigned to a "
                  "deductible category?" % (len(uncat), names))
    biggest = max(receipts, key=lambda r: r.amount, default=None)
    if biggest is not None:
        qs.append("Largest single expense: %s at %.2f %s - is this a capital "
                  "asset rather than a one-off cost?" % (biggest.vendor,
                                                         biggest.amount,
                                                         biggest.currency))
    curs = sorted({r.currency for r in receipts})
    if len(curs) > 1:
        qs.append("Expenses span %s - which exchange rate applies on the tax "
                  "return?" % ", ".join(curs))
    if not qs:
        qs.append("No open questions - everything is categorised and single-currency.")
    return qs


def write_csv(receipts, path):
    import csv as _csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["date", "vendor", "amount", "currency", "category", "note", "source"])
        for r in receipts:
            w.writerow([r.date, r.vendor, "%.2f" % r.amount, r.currency,
                        r.category, r.note, r.source])
    return path


_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LocalLedger - __TITLE__</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f7f9;color:#1a1f2b;margin:0;padding:24px}
 .card{max-width:900px;margin:0 auto;background:#fff;border:1px solid #e3e6ea;border-radius:12px;padding:24px}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:22px 0 8px;color:#374151}
 .sub{color:#6b7280;font-size:13px;margin:0 0 16px}
 .pill{display:inline-block;background:#eef2ff;color:#3730a3;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:600}
 table{border-collapse:collapse;width:100%;margin-top:8px}
 th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #eef0f3;font-size:13.5px}
 th{color:#5a6472;font-weight:600}
 .tot{font-weight:700}
 .note{background:#f9fafb;border-left:3px solid #4f7cff;border-radius:0 8px 8px 0;padding:10px 14px;font-size:14px;line-height:1.5}
 ol{padding-left:20px;font-size:14px;line-height:1.6}
 .bar{height:8px;background:#eef2ff;border-radius:4px;overflow:hidden}
 .bar>span{display:block;height:100%;background:#4f7cff}
</style></head><body><div class="card">
<h1>LocalLedger</h1>
<p class="sub">__TITLE__ &middot; engine: <span class="pill">__ENGINE__</span></p>
<div class="note">__NARRATIVE__</div>
<h2>Summary</h2>
<table><tbody>__SUMMARY_ROWS__</tbody></table>
<h2>Spending by category</h2>
<table><thead><tr><th>Category</th><th>Amount (__PRIMARY__)</th><th></th></tr></thead><tbody>__CAT_ROWS__</tbody></table>
<h2>Documents read</h2>
<table><thead><tr><th>Date</th><th>Vendor</th><th>Amount</th><th>Category</th><th>Note</th></tr></thead><tbody>__DOC_ROWS__</tbody></table>
<h2>Questions to ask your accountant</h2>
<ol>__QUESTIONS__</ol>
<p class="sub">Generated on-device by LocalLedger. No receipt data was transmitted.</p>
</div></body></html>"""


def _row(cells):
    return "<tr>" + "".join("<td>%s</td>" % _html.escape(str(c)) for c in cells) + "</tr>"


def html_report(summary, receipts, path, title="Quarterly review"):
    totals = summary["totals"]
    sum_rows = "".join(
        _row([("%s total" % c), "<span class='tot'>%.2f %s</span>" % (v, c)])
        for c, v in sorted(totals.items()))
    sum_rows += _row(["Documents", summary["count"]])
    sum_rows += _row(["Uncategorised", summary["uncategorized"]])
    top = summary["ranked"][0][1] if summary["ranked"] else 0.0
    cat_rows = ""
    for cat, amt in summary["ranked"]:
        width = 0 if not top else int(round(100.0 * amt / top))
        cat_rows += ("<tr><td>%s</td><td class='tot'>%.2f</td>"
                     "<td><div class='bar'><span style='width:%d%%'></span></div></td></tr>"
                     % (_html.escape(cat), amt, width))
    doc_rows = "".join(
        _row([r.date or "-", r.vendor, "%.2f %s" % (r.amount, r.currency),
              r.category, r.note]) for r in receipts)
    questions = "".join("<li>%s</li>" % _html.escape(q)
                        for q in accountant_questions(receipts))

    doc = _HTML
    for key, val in (("__TITLE__", _html.escape(title)),
                     ("__ENGINE__", _html.escape(summary["engine"])),
                     ("__NARRATIVE__", _html.escape(summary["narrative"])),
                     ("__SUMMARY_ROWS__", sum_rows),
                     ("__PRIMARY__", _html.escape(summary["primary_currency"])),
                     ("__CAT_ROWS__", cat_rows),
                     ("__DOC_ROWS__", doc_rows),
                     ("__QUESTIONS__", questions)):
        doc = doc.replace(key, val)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path
