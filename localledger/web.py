"""Tiny stdlib web console. Shows the on-device scan result with no upload."""
from __future__ import annotations

import html as _html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import parse_file, summarize, accountant_questions
from .llm import get_model

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LocalLedger console</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f7f9;color:#1a1f2b;margin:0;padding:24px}
 .card{max-width:900px;margin:0 auto;background:#fff;border:1px solid #e3e6ea;border-radius:12px;padding:24px}
 h1{font-size:20px;margin:0 0 4px}
 .sub{color:#6b7280;font-size:13px;margin:0 0 16px}
 .pill{display:inline-block;background:#eef2ff;color:#3730a3;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:600}
 table{border-collapse:collapse;width:100%;margin-top:8px}
 th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #eef0f3;font-size:13.5px}
 th{color:#5a6472;font-weight:600}
 .note{background:#f9fafb;border-left:3px solid #4f7cff;border-radius:0 8px 8px 0;padding:10px 14px;font-size:14px;line-height:1.5}
 ol{padding-left:20px;font-size:14px;line-height:1.6}
</style></head><body><div class="card">
<h1>LocalLedger</h1>
<p class="sub">On-device invoice &amp; receipt organizer &middot; engine: <span class="pill">__ENGINE__</span></p>
<div class="note">__NARRATIVE__</div>
<h2 style="font-size:15px;margin:22px 0 8px;color:#374151">Totals</h2>
<table><tbody>__TOTALS__</tbody></table>
<h2 style="font-size:15px;margin:22px 0 8px;color:#374151">Documents read</h2>
<table><thead><tr><th>Date</th><th>Vendor</th><th>Amount</th><th>Category</th><th>Note</th></tr></thead><tbody>__DOCS__</tbody></table>
<h2 style="font-size:15px;margin:22px 0 8px;color:#374151">Questions to ask your accountant</h2>
<ol>__QUESTIONS__</ol>
<p class="sub">Nothing was uploaded. This page was rendered from a file on the server's own disk.</p>
</div></body></html>"""


def _esc(v):
    return _html.escape(str(v))


def render(example, use_llm=True):
    receipts = parse_file(example)
    summary = summarize(receipts, model=get_model(enabled=use_llm))
    totals = "".join("<tr><td>%s</td><td><strong>%.2f %s</strong></td></tr>"
                     % (_esc(k), v, _esc(k)) for k, v in sorted(summary["totals"].items()))
    docs = "".join(
        "<tr><td>%s</td><td>%s</td><td>%.2f %s</td><td>%s</td><td>%s</td></tr>"
        % (_esc(r.date or "-"), _esc(r.vendor), r.amount, _esc(r.currency),
           _esc(r.category), _esc(r.note)) for r in receipts)
    questions = "".join("<li>%s</li>" % _esc(q) for q in accountant_questions(receipts))
    page = PAGE
    for key, val in (("__ENGINE__", _esc(summary["engine"])),
                     ("__NARRATIVE__", _esc(summary["narrative"])),
                     ("__TOTALS__", totals),
                     ("__DOCS__", docs),
                     ("__QUESTIONS__", questions)):
        page = page.replace(key, val)
    return page


def make_handler(example, use_llm=True):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/healthz"):
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
                return
            try:
                page = render(example, use_llm=use_llm)
                code = 200
            except Exception as exc:  # pragma: no cover - defensive
                page = "<h1>LocalLedger</h1><p>error: %s</p>" % _esc(exc)
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))

    return Handler


def serve(port, example="examples/receipts.txt", host="0.0.0.0"):
    if not os.path.exists(example):
        raise SystemExit("example file not found: %s" % example)
    srv = ThreadingHTTPServer((host, int(port)), make_handler(example))
    print("LocalLedger console -> http://%s:%s/  (health: /healthz)" % (host, port))
    srv.serve_forever()
