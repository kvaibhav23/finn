# Spike 02: NSE corporate announcements (portfolio × date window)

**Verdict: PASS.** Plain HTTP works: 6/6 symbols, 2/2 market-wide days and 2/2 attachments, all HTTP 200, with no 403s on the API.

Run: `python spikes/02_nse_announcements/run.py`. First live run: 2026-11-01 ~01:48 IST. The re-run made 0 live requests.
Window: 01-Oct-2026 to 31-Oct-2026 (results season, so it's a busy month).

## What worked
- **A. Per symbol:** `GET https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=X&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY`
  - Returns a JSON list. 94 announcements across 6 symbols: RELIANCE 18, TCS 19, HDFCBANK 18, ASIANPAINT 13, DIXON 12, KPITTECH 14.
  - Latency 585–761 ms, 8–14 KB per call.
- **B. Whole market, one day per call:** same endpoint with no `symbol`.
  - 30-Oct: 955 rows (666 KB, 1,359 ms). 31-Oct: 481 rows (332 KB, 1,255 ms).
  - **Cross-check:** the market feed held 100% of what the per-symbol calls returned for those days (9/9 and 4/4).
- **C. Attachments:** 94/94 rows have a PDF URL on `nsearchives.nseindia.com/corporate/…`.
  - These downloaded from a plain session with no cookies: 200, `%PDF-` magic bytes.
  - 239 KB in 510 ms; 2.07 MB in 2,561 ms.
- **Cookie warm-up:**
  - `GET https://www.nseindia.com/` itself returned **403** (368 bytes).
  - It still set Akamai cookies (`_abck, ak_bmsc, bm_sv, bm_sz, AKA_A2`), and every API call after it returned 200.
  - We did **not** test the API without the warm-up; we're not probing the bot defences.

## HTTP status and latency
| call | status | latency | bytes |
|---|---|---|---|
| warm-up (home page) | 403 | 402 ms | 368 |
| per-symbol × 6 | 200 ×6 | 585–761 ms | 8.5–14 KB |
| market-wide 30-Oct | 200 | 1,359 ms | 666,675 |
| market-wide 31-Oct | 200 | 1,255 ms | 332,244 |
| PDF (concall audio notice) | 200 | 510 ms | 238,960 |
| PDF (investor presentation) | 200 | 2,561 ms | 2,074,192 |
| RSS `Online_announcements.xml` (fallback test) | 200 | 411 ms | 1,175 (only 1 item) |

## Fields
- **Returned:** `seq_id, symbol, sm_name, sm_isin, smIndustry, desc, attchmntText, an_dt, dt, sort_date, exchdisstime, difference, attchmntFile, attFileSize, fileSize, hasXbrl, bflag, csvName, old_new, orgid`
- **Useful:**
  - `seq_id`: unique in all 94 rows. **It's the only safe dedupe key.** (symbol, an_dt) repeats 4 times, because one board outcome can be filed as 2 PDFs, and KPIT filed 4 categories in the same second.
  - `desc`: the NSE category, a coarse materiality signal.
  - `attchmntText`: the subject line, sometimes a rich summary (for example, RIL's board outcome lists results plus a Rs 15,000 crore NCD enabling resolution).
  - `an_dt` and `exchdisstime`: filing and dissemination times. The lag is 0–2 s, so filings are effectively real time.
  - `attchmntFile`: the PDF URL.
  - `sm_isin`: joins to spike 01.
- **Always null (100%):** `bflag, csvName, old_new, orgid`.
- **`smIndustry`:** null in 28% of rows.
- **`hasXbrl`:** `True` on all 94 rows, so it carries **no signal**.

## Sample output
| symbol | desc | an_dt | attchmntText (truncated) |
|---|---|---|---|
| RELIANCE | Outcome of Board Meeting | 30-Oct-2026 19:40:11 | approved the unaudited Financial Results … enabling resolution … NCDs up to Rs. 15,000 crore |
| RELIANCE | Other Restructuring | 29-Oct-2026 08:55:40 | Voluntary strike off of Hamleys (Franchising) Limited |
| TCS | Analysts/Institutional Investor Meet/Con. Call Updates | 14-Oct-2026 16:00:08 | … has informed the Exchange about Transcript |
| KPITTECH | Acquisition | 28-Oct-2026 13:28:05 | (filed alongside Appointment / Guarantee / Sale-or-disposal, same second) |

## Category mix over 94 rows: implications for materiality ranking
- **Probable noise, droppable by category:** 14/94 (15%). Copy of Newspaper Publication 9, Depositories certificate 5.
- **Vague buckets that need the subject or PDF to judge:** 21/94 (22%). General Updates 12, Updates 9.
- **High-signal categories:** Outcome of Board Meeting 10, Acquisition 2, Sale or disposal 1, Change in Management 2, Credit Rating 1, Action(s) taken or orders passed 1, Dividend 2, Restructuring 1, and others.
- **Analyst/concall updates:** 19. Only 2 subjects say "Transcript" (TCS, HDFCBANK), while 6 are meeting schedules.
  - The RSS item showed a finer subject: "Transcripts - earnings or quarterly call". This feeds spike 07.

## What failed or wasn't confirmed
- **RSS fallback:** `nsearchives…/RSS/Online_announcements.xml` holds only the single latest item, so it's no use as a backfill. Its link points to a per-announcement XBRL file (`corporate/xbrl/…WebXMLFile…xml`), which is worth a look in spike 05.
- **Market-wide row cap or pagination:** none observed (955 rows on a peak day). Completeness is checked only for our 6 symbols on 2 days.

## Missing fields
- No severity or materiality flag from NSE.
- No structured event fields (amount, counterparty). These would have to come from the subject text or PDF.

## Recommended approach and fallback
- **Primary:** the market-wide call, once per day (plus intraday polls if needed), filtered locally.
  - 1 request per day covers **any** number of portfolios and users.
  - The per-symbol pattern costs N requests per window.
- **Use per-symbol** only for historical backfill of a single ticker (any window in one call).
- **Fallback:** BSE announcements (deferred under the NSE-only decision; Akamai-protected), or company IR pages. The RSS feed is not a viable fallback.
- **Operational risks:**
  - Akamai cookies expire, so re-warm on 401/403 with a backoff.
  - The undocumented API and NSE's website terms are a standing risk, to note in the architecture.

## Proposed signature
```python
def get_announcements(start: date, end: date, symbols: list[str] | None = None) -> pd.DataFrame:
    """One row per seq_id. Columns: seq_id, symbol, isin, name, industry, category (desc),
    subject (attchmntText), filed_at (an_dt, IST), disseminated_at, pdf_url, pdf_size.
    symbols=None -> whole market, fetched one day per request and cached per day."""
```
