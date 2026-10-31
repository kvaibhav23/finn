# Spike 06: annual reports (find, download, extract)

**Verdict: PASS for discovery, download and text extraction.**
- All 6 tickers are listed, with 8–19 years each.
- 4/4 test reports downloaded, including 1 ZIP.
- None was scanned, and pymupdf extracts a 361–520-page report in under 2 s.

**Table extraction: UNRELIABLE.** This doesn't block anything, because financial numbers come from XBRL (spike 05).

Run: `python spikes/06_annual_reports/run.py`. First live run: 2026-11-01 ~02:01 IST. The re-run is served from cache.

## What worked
- **Listing:** `GET https://www.nseindia.com/api/annual-reports?index=equities&symbol=X` → `{"data": [...]}`, newest first.
  - Fields: `fromYr, toYr, fileName (URL), broadcast_dttm, disseminationDateTime, submission_type, attFileSize`.
  - 159–437 ms, after the usual home-page warm-up (which returns 403 but sets cookies).

| symbol | reports | range | latest filed | latest size | formats |
|---|---|---|---|---|---|
| RELIANCE | 17 | FY10 → FY26 | 28-May-2026 | 10.50 MB | 3 pdf, 14 zip |
| TCS | 17 | FY10 → FY26 | 15-May-2026 | 16.62 MB | 2 pdf, 15 zip |
| HDFCBANK | 18 | FY10 → FY26 | 11-Jul-2026 | 12.08 MB | 4 pdf, 14 zip |
| ASIANPAINT | 19 | FY09 → FY26 | 12-Jun-2026 | 25.06 MB | 3 pdf, 16 zip |
| DIXON | 9 | FY18 → FY26 | 03-Sep-2026 | 14.77 MB | 3 pdf, 6 zip |
| KPITTECH | 8 | FY19 → FY26 | 05-Aug-2026 | 9.82 MB | 3 pdf, 5 zip |

- **Downloads:** `nsearchives.nseindia.com/annual_reports/…`, plain session, no cookies.
  - **PDF from about FY24 onwards, ZIP before.** The ZIP tested holds a single PDF.
  - **Metadata quirks:** older rows have `broadcast_dttm = "-"` and `attFileSize = None`.

| report | size | download | pages | pymupdf time | chars | low-text pages | MD&A header pages | consolidated P&L pages |
|---|---|---|---|---|---|---|---|---|
| TCS FY26 (pdf) | 17.4 MB | 9,265 ms | 361 | 1.6 s | 1,082,954 | 1 (cover) | 42–70 | 158–238 |
| DIXON FY26 (pdf) | 15.5 MB | 5,220 ms | 520 | 1.9 s | 1,439,594 | 4 (last pages) | 75–220 | 409–426 |
| DIXON FY24 (pdf) | 12.2 MB | 3,649 ms | 378 | 0.9 s | 1,163,451 | 5 | 30–190 | 291–305 |
| KPITTECH FY23 (zip) | 4.1 MB | 2,731 ms | 345 | 0.8 s | 1,023,282 | 7 (5 with images) | 43–94 | 231–253 |

- **No scanned reports.** Low-text pages (under 100 chars) are covers and back pages: 1–7 per report. **OCR is not needed.**
- **Mechanical cross-check against XBRL:**
  - TCS FY26 consolidated `RevenueFromOperations` from the Q4 integrated XBRL (12-month context) is 2,670,210,000,000 INR = ₹267,021 cr.
  - It appears in the report text as "267,021" (pages 9, 25, 59, 60, 70) and as "2,67,021" (pages 36, 37, 110, 168, 211, 226). Page 168 is the consolidated P&L.
- **Section location:** running headers make page ranges findable by plain regex, e.g. "Management Discussion and Analysis" or "Consolidated Statement of Profit and Loss". The first hit is usually the table of contents (TCS page 4).

## pymupdf vs pdfplumber (same first 25 pages)
| report | pymupdf | pdfplumber | pdfplumber, full doc (est.) |
|---|---|---|---|
| TCS FY26 | 4 ms/page, 100,759 chars | 140–147 ms/page, 98,085 chars | about 51–53 s |
| DIXON FY26 | 4 ms/page, 87,660 chars | 126–128 ms/page, 84,469 chars | about 66 s |
| DIXON FY24 | 2 ms/page, 98,206 chars | 99–102 ms/page, 95,744 chars | about 37–39 s |
| KPITTECH FY23 | 2 ms/page, 41,675 chars | 252 ms/page, 40,374 chars | about 87 s |

**Use pymupdf for text.** It's 30–100× faster with about 3% more characters. Use pdfplumber only for a specific table page, if ever needed.

## What failed: tables
On the consolidated P&L page, each library found 1 table per report, but:
- **TCS:** pdfplumber read the revenue row cleanly (`['Revenue from operations', '12', '2,67,021', '2,55,324']`). pymupdf mangled the Indian-format numbers (`'267021\n, ,'`).
- **DIXON FY26, DIXON FY24, KPITTECH FY23:** **neither library** put "Revenue from operations" inside a detected table. The row sits outside the detected table, as loose text lines.

Conclusion: PDF tables are layout-dependent and can't be a numbers source. This confirms the rule: numbers come from XBRL, and annual reports supply narrative only.

## Missing fields
- No section index or bookmarks were used: they weren't checked here; `doc.get_toc()` would be the next thing to try.
- No per-section metadata from NSE.
- The listing has no "revised report" or "integrated report vs annual report" distinction beyond `submission_type`.
- **Timing:** annual reports arrive 1.5–5 months after the fiscal year ends (TCS 15 May; DIXON 3 Sep). That's too late for the push digest; they serve the pull research only.

## Cost (this matters for LLM spend)
- **Download:** 1 listing plus one 4–25 MB file per company-year, cached forever.
  - 3 years × 20 stocks ≈ 60 files ≈ 0.6–1 GB.
  - Disk is the main cost; consider keeping only the extracted text.
- **Extraction:** about 2 s per report (pymupdf), 0 tokens.
- **LLM:** one report is 1.0–1.4 million chars, roughly 250k–360k tokens. **Never send a whole report.**
  - Target sections by header page ranges: MD&A, the Chairman's letter, risks, and outlook.
  - Then retrieve passages. That's likely under 5% of the pages per question.

## Fallback
- **Company IR site** (URL not in NSE data; would need a per-company mapping).
- **BSE annual-report listing** (deferred under the NSE-only decision).
- **For ZIPs with several PDFs:** the script picks the largest member. Only single-PDF ZIPs were seen.

## Terms-of-use and stability risk
- The listing is an undocumented NSE API (cookie-gated).
- The files sit on static `nsearchives` URLs (low risk).
- Large files: use long timeouts. Downloads of 9 s were seen; the timeout is 30 s per socket read.

## Proposed signature
```python
def get_annual_report(symbol: str, fiscal_year_start: int) -> dict:
    """-> {"symbol", "fy": "2025-26", "url", "filed_at", "pages": [str, ...] (pymupdf text per page),
    "sections": {"mdna": (first_page, last_page), "consolidated_pl": (...), ...}}.
    Handles PDF and ZIP. Raises LookupError if not listed."""

def list_annual_reports(symbol: str) -> list[dict]:  # fy, url, filed_at, size
```
