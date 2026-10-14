"""Command line interface for LocalLedger."""
from __future__ import annotations

import argparse
import os
import sys

from .core import (parse_file, summarize, write_csv, html_report,
                   accountant_questions)
from .llm import get_model


def _print_table(receipts):
    if not receipts:
        print("  (no documents parsed)")
        return
    w = max(len(r.vendor) for r in receipts)
    w = max(w, 6)
    print("  %-10s  %-*s  %10s  %-13s  %s" % ("DATE", w, "VENDOR", "AMOUNT", "CATEGORY", "NOTE"))
    print("  " + "-" * (w + 46))
    for r in receipts:
        print("  %-10s  %-*s  %6.2f %-3s  %-13s  %s"
              % (r.date or "-", w, r.vendor, r.amount, r.currency, r.category, r.note[:38]))


def cmd_scan(args):
    if not os.path.exists(args.path):
        print("error: no such file: %s" % args.path, file=sys.stderr)
        return 2
    receipts = parse_file(args.path)
    model = get_model(enabled=not args.no_llm)
    summary = summarize(receipts, model=model)

    print("LocalLedger - scanning %s" % args.path)
    print("engine: %s" % summary["engine"])
    print()
    _print_table(receipts)
    print()
    print("  Totals: " + ", ".join("%.2f %s" % (v, k)
                                   for k, v in sorted(summary["totals"].items())))
    print("  Documents: %d   Uncategorised: %d"
          % (summary["count"], summary["uncategorized"]))
    print()
    print("Narrative")
    print("  " + summary["narrative"])
    print()
    print("Questions to ask your accountant")
    for q in accountant_questions(receipts):
        print("  - " + q)

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "ledger.csv")
    html_path = os.path.join(args.out, "quarterly-review.html")
    write_csv(receipts, csv_path)
    html_report(summary, receipts, html_path, title=args.title)
    print()
    print("Wrote %s" % csv_path)
    print("Wrote %s" % html_path)
    return 0


def cmd_serve(args):
    from .web import serve
    serve(os.environ.get("PORT") or args.port, example=args.path, host=args.host)
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="localledger",
        description="Offline invoice & receipt organizer for freelancers.")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("scan", help="scan a receipts file and write exports")
    s.add_argument("path", help="path to a plain-text receipts file")
    s.add_argument("--out", default="out", help="output directory (default: out)")
    s.add_argument("--no-llm", action="store_true",
                   help="force the deterministic offline engine")
    s.add_argument("--title", default="Quarterly review")
    s.set_defaults(func=cmd_scan)

    w = sub.add_parser("serve", help="run the local web console")
    w.add_argument("--port", default="8780")
    w.add_argument("--host", default="0.0.0.0")
    w.add_argument("--path", default="examples/receipts.txt")
    w.set_defaults(func=cmd_serve)
    return p


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)
