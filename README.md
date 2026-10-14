# LocalLedger

**An offline invoice and receipt organizer for freelancers.**
Point it at a folder of receipts; it reads them *on your own laptop*, categorises
every line, writes an accounting-ready CSV and a plain-language quarterly review,
and tells you what to ask your accountant. **Nothing is uploaded — ever.**

Built for the [Hacktoberfest 2026 DEV Challenge](https://dev.to/challenges) — Week 2, *Side Hustle*.

> Traditional bookkeeping tools want your bank feed, your receipts and your OCR
> in their cloud. For a freelancer that means client names, rates and bank details
> leaving the machine for a monthly subscription. LocalLedger flips it: the whole
> thing runs locally on open-weight models, so the data never moves and the cost
> per receipt is zero.

---

## Why open source AI matters here (the part judges ask about)

Freelancers handle **other people's** financial data. Three things break with a closed cloud OCR service:

1. **Privacy.** Client invoices contain names, addresses and amounts. A local
   open-weight model keeps them on disk. No API, no data-processing agreement, no
   breach surface.
2. **Cost.** Cloud document-AI charges per page. A freelancer with 400 receipts a
   year either eats that margin or passes it on. Local inference has **zero
   marginal cost per document**, which is what makes a $5–10/month price work.
3. **Fit.** A local model can be fine-tuned on *your* vendor names and categories.
   A generic API cannot learn that "ACME DSGN" is your biggest client.

LocalLedger therefore has **two interchangeable engines**:

| Engine | When it runs | What it does |
|---|---|---|
| `deterministic-offline` | Always available | Regex parser + keyword categories. Works with **zero setup**, no model, no network. |
| `local-open-weight-model` | When [Ollama](https://ollama.com) (or any OpenAI-compatible server) is reachable on localhost | Writes the quarterly narrative in plain English from the parsed rows. |

The parsing and categorising are **plain code, not the model** — the model only
writes prose. That keeps the numbers auditable and the tool honest: it will not
invent a total.

---

## Quick start

Requires **Python 3.8+**. No third-party packages.

```bash
# 1. scan a receipts file and write out/ledger.csv + out/quarterly-review.html
python -m localledger scan examples/receipts.txt --no-llm

# 2. or run the local web console
python -m localledger serve --port 8780
#    then open http://127.0.0.1:8780/
```

Expected output (excerpt):

```
LocalLedger - scanning examples/receipts.txt
engine: deterministic-offline

  DATE        VENDOR                     AMOUNT  CATEGORY       NOTE
  ------------------------------------------------------------------
  2026-07-03  ADOBE SYSTEMS INCORPORATED  22.99 USD  Software   Creative Cloud - monthly subscri…
  2026-07-07  UBER TRIP                   18.40 USD  Travel     Ride to client meeting downtown
  2026-07-09  STARBUCKS STORE 1042         6.75 USD  Meals      Team coffee meeting
  2026-07-14  AMAZON MARKETPLACE          31.20 USD  Office     Printer paper and toner
  2026-07-21  LUFTHANSA                  210.50 EUR  Travel     Flight FRA-LHR return
  ...
  Totals: 224.33 USD, 210.50 EUR, 14.99 GBP
```

### Optional: turn on the local model

```bash
ollama pull gemma2:2b          # an open-weight model
python -m localledger scan examples/receipts.txt
# engine: local-open-weight-model
```

Override the endpoint/model with `LOCALLLM_URL` and `LOCALLLM_MODEL`
(works with Ollama, llama.cpp, vLLM, LM Studio). If nothing is reachable the tool
silently falls back to the deterministic engine — **it never fails on a fresh machine.**

---

## What you get

- **`out/ledger.csv`** — `date, vendor, amount, currency, category, note, source`.
  Drop it straight into your accounting import.
- **`out/quarterly-review.html`** — totals per currency, spending by category with
  bars, every document read, and the accountant question list.
- **Accountant questions** — derived from *your* data, e.g. the meals-deductibility
  line, uncategorised items, the largest single expense, and multi-currency FX.

Everything is cited: each parsed row carries an `evidence` trail
(`<file>:<line> vendor=… / date=… / amount=…`), so a number can always be traced
back to the line it came from.

---

## Design

```
receipts.txt ──▶ parse (regex, per block)  ──▶ categorise (keyword rules)
                      │                              │
                      └──────────▶ Receipt[] ────────┘
                                        │
                     ┌──────────────────┴──────────────────┐
                     ▼                                     ▼
          deterministic narrative              local open-weight model
                     └──────────────────┬──────────────────┘
                                        ▼
                        write_csv()  ●  html_report()  ●  accountant_questions()
```

- `localledger/core.py` — parsing, categorising, summarising, CSV + HTML report.
- `localledger/llm.py` — local open-weight model bridge (Ollama / OpenAI-compatible).
- `localledger/cli.py` — `scan` and `serve` commands.
- `localledger/web.py` — stdlib `ThreadingHTTPServer` console (reads `PORT`).
- `eval.py` — 40+ assertions, offline, no network.

## Tests

```bash
python eval.py     # all assertions should pass
```

## License

MIT — see [LICENSE](LICENSE).
