# FINN data spikes: summary

**Date:** 2026-11-01

**Scope:** can FINN's push digest and pull research run on primary sources, using plain HTTP, politely and cheaply?

**Answer: yes, on NSE alone.**
- Every data need has a working source, and none needs a headless browser, OCR, or an LLM to produce numbers.
- The sample was 6 tickers (RELIANCE, TCS, HDFCBANK, ASIANPAINT, DIXON, KPITTECH), defined in `spikes/tickers.py`.
- The detailed evidence is in each `spikes/NN_*/REPORT.md`.

## Results
| # | spike | verdict | primary source | fallback |
|---|---|---|---|---|
| 01 | symbol master | **PASS** (NSE-only) | NSE `EQUITY_L.csv`: 2,620 symbols + ISIN, 1 request | NSE quote API; BSE deferred |
| 02 | corporate filings | **PASS** | NSE `/api/corporate-announcements`; **market-wide, 1 request/day** covers every portfolio | BSE (deferred); RSS is **not viable** (1 item) |
| 03 | BSE filings | **SKIPPED** | BSE API returns 403 to plain requests (Akamai). Decision: NSE-only | — |
| 04 | EOD price / volume / delivery % | **PASS** | NSE UDiFF bhavcopy: whole market, 1 file/day, published about 16:33 IST | yfinance (matched 18/18 exactly) |
| 05 | quarterly financials | **PASS** | NSE XBRL: legacy listing (2005→Dec-24) + Integrated Filing (Mar-25→now) | iXBRL HTML of the same filing |
| 06 | annual reports | **PASS** (text) / tables unreliable | NSE `/api/annual-reports` → PDF/ZIP, pymupdf text | company IR site |
| 07 | concall transcripts | **PASS** (discovery, text, speakers) / guidance regex partial | filings from 02, filtered by "transcript" | company IR site |

## Source per data need
| FINN need | source | latency to availability | format |
|---|---|---|---|
| Push: new filings | market-wide announcements feed | 0–2 s from filing (`an_dt` → `exchdisstime`) | JSON + PDF |
| Push: price/volume alerts | UDiFF bhavcopy | about 16:33 IST (about 1 h after close) | zip/csv |
| Push: delivery-% signal | `sec_bhavdata_full` | about 23:55 IST | csv |
| Pull: financial actuals | XBRL (Integrated Filing + legacy) | same evening as results | XML |
| Pull: management guidance | transcripts | about 3–7 days after the call | PDF |
| Pull: narrative, strategy, risks | annual report | 1.5–5 months after fiscal year-end | PDF / ZIP |

## Cost for a 20-stock portfolio (requests to NSE)
| cadence | requests | volume |
|---|---|---|
| Daily | about 3–4: 1 cookie warm-up, 1 market-wide filings call, 1 bhavcopy (+1 delivery file), plus only the filing PDFs worth opening | about 1 MB + PDFs |
| Per quarter | about 40 for financials (20 listings + 20 XBRL), plus about 20 transcript PDFs (discovered for free in the daily feed) | about 15 MB |
| Per year | about 20 annual reports | about 0.3 GB (keep the extracted text, drop the PDFs?) |
| One-off backfill (3 years) | about 280 XBRL + about 60 ARs + about 750 bhavcopies | about 1–1.5 GB, cached forever |

The market-wide feed and the bhavcopy cost the same for 1 user or 10,000, so marginal cost per user is about zero. **The LLM is the only variable cost**, which is where the architecture has to be careful:
- **Annual reports:** about 250k–360k tokens each, so **never send them whole**. Target sections by their running headers (MD&A, risks, outlook), then retrieve passages.
- **Transcripts:** regex picks 5–20 candidate guidance sentences, and the LLM classifies **only those** (about 1–2k tokens per call instead of 15–35k).
- **Filings:**
  - About 15% can be dropped by category alone (newspaper copies, depositories certificates).
  - About 22% sit in vague "Updates" categories. These go to the LLM on the subject line first, and the PDF only if needed.
  - High-signal categories (board outcome, acquisition, rating, management change …) rank on rules.

## Proposed data layer (signatures from the reports)
```python
resolve_symbol(nse_symbol) -> dict                                   # 01
get_announcements(start, end, symbols=None) -> DataFrame             # 02: dedupe on seq_id
get_eod(day, with_delivery=False) -> DataFrame | None                # 04: None = not a trading day
get_quarterly_financials(symbol, n_quarters=12, basis="Consolidated") -> DataFrame   # 05: value + xbrl tag + url
list_annual_reports(symbol) / get_annual_report(symbol, fy) -> dict  # 06: pages + section ranges
find_transcripts(symbol, start, end) / parse_transcript(pdf) / guidance_candidates(parsed)   # 07
```
Every number keeps its receipt (XBRL tag + file URL). Every quote keeps its page and speaker. That's what the promise ledger shows the user.

## Traps found (each would silently corrupt output if missed)
1. **Legacy XBRL mislabels YTD as quarterly.** The `FourD` context declares quarter dates but holds 9-month values. Validate against the filing's own `DateOfStartOfReportingPeriod`. (05)
2. **Zero means "not reported".** Consolidated bank filings tag GNPA %, CET1 and ROA as `0`. (05)
3. **EPS series breaks with share-count changes:** HDFCBANK went from 23.11 to about 13 while PAT rose. Per-share trends need corporate-action adjustment, or should use absolute PAT. (05)
4. **Two taxonomies:** banks have no `RevenueFromOperations`. Line items need a per-taxonomy map. (05)
5. **NSE's results listing silently stops at Dec-2024:** newer quarters moved to Integrated Filing. A naive client would think results stopped. (05)
6. **`hasXbrl` is True on every announcement,** so it carries no signal. **`(symbol, time)` isn't unique,** so dedupe on `seq_id`. (02)
7. **Broken PDF ligatures** (`OƯicer`) break verbatim quotes and search, so normalise before quoting. (07)
8. **Today's bhavcopy 404 means "not yet published"; a past date's 404 means "holiday".** Only the latter may be cached. (04)
9. **PDF tables are layout-dependent:** 3 of 4 annual reports put the revenue row outside the detected table. Never take numbers from PDFs. (06)

## Risks and open items
- **Undocumented NSE APIs.** The `/api/*` endpoints are undocumented, cookie-gated, and behind Akamai.
  - The home page returns 403 but still sets cookies, and APIs then work. Cookies expire, so re-warm on 401/403 with a backoff.
  - **NSE's website terms restrict automated access.** For a production product, licensed data (an NSE data feed or a vendor) is the clean route; the archive files (`nsearchives`) carry lower risk.
- **BSE is deferred.** It blocks plain requests, and the decision is NSE-only. The `bse` package worked in a one-off test, if ever needed.
- **SME-board symbols** are missing from `EQUITY_L.csv`, though present in the bhavcopy. "Any NSE ticker" is mainboard-only for now.
- **Cache policy for live data:** the spike cache never re-downloads by design. Production needs per-day keys for "today" feeds.
- **Transcript discovery misses (ASIANPAINT Mar-26),** name-variant merging, and new transcript layouts each need monitoring: alert on "0 turns parsed".
- **Not measured:** intraday filing-feed polling behaviour and rate limits under sustained load (spike scale was about 60 requests per run).

## Suggested next step
A thin promise-ledger prototype for 1–2 tickers, chaining the existing pieces:
1. Transcript → guidance candidates (07).
2. LLM structures candidates into {metric, target, deadline}.
3. Match against XBRL actuals (05) for the deadline quarter.
4. Show the verbatim quote + page next to the XBRL value + tag.

ASIANPAINT's "18–20% PBDIT margin" guidance is a ready test case, because the inputs are all in XBRL.
