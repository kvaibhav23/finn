# Spike 07: earnings-call transcripts (input for the promise ledger)

**Verdict: PASS.**
- **Discovery:** 30 transcript filings found across 6 tickers over 13 months. Every completed quarter is covered except 1 (ASIANPAINT, Mar-26).
- **Text:** 6/6 have a real text layer. OCR is not needed.
- **Speaker segmentation:** 6/6 transcripts split into turns, across 2 distinct layouts.
- **Verbatim receipts with page numbers:** demonstrated.

**Guidance extraction by regex alone: PARTIAL.** It's a good candidate filter, but not a classifier (see below).

Run: `python spikes/07_concall_transcripts/run.py`. First live run: 2026-11-01 ~02:04 IST. The re-run made 0 live requests.
Window: 01-Oct-2025 to 31-Oct-2026, via the per-symbol announcements endpoint from spike 02.

## Discovery
- **Method:** fetch all announcements per symbol for the window (1 request each, 128–209 rows), then keep rows whose subject (`attchmntText`) contains "transcript".
- **Categories:** 29 of 30 filings sit under "Analysts/Institutional Investor Meet/Con. Call Updates", and 1 under "Updates" (ASIANPAINT). **Don't filter by category alone.**
- **Subjects vary:** generic ("…has informed the Exchange about Transcript", used by TCS, HDFCBANK and DIXON) or descriptive (RELIANCE, KPITTECH).
- **Non-earnings hits** were classified by subject and excluded: an ASIANPAINT AGM transcript, and an ASIANPAINT investor conference held on 3 Jun.

**Earnings-transcript coverage by results quarter:**

| symbol | Sep-25 | Dec-25 | Mar-26 | Jun-26 | Sep-26 |
|---|---|---|---|---|---|
| RELIANCE | 1 | 1 | 1 | 1 | 0 (call 30-Oct, not yet filed) |
| TCS | 3 | 1 | 1 | 1 | 1 |
| HDFCBANK | 1 | 2 | 1 | 1 | 1 |
| ASIANPAINT | 1 | 1 | **0** | 1 | 0 (call 29-Oct) |
| DIXON | 1 | 1 | 1 | 1 | 0 (call 30-Oct) |
| KPITTECH | 1 | 1 | 1 | 1 | 0 (call 28-Oct) |

- **Sep-26 zeros are expected:** these calls were held 28–30 Oct, and the filing deadline is a few working days after the call.
- **The ASIANPAINT Mar-26 gap is unexplained.** Its subject line may not contain "transcript"; this wasn't investigated.
- **Duplicates:** quarters with 2–3 entries (TCS Sep-25, HDFCBANK Dec-25) are repeat or corrected filings, or other analyst meets. The pipeline must dedupe per quarter, e.g. by keeping the latest filing.

## Download and text
| symbol | quarter | size | pages | chars | low-text pages | layout |
|---|---|---|---|---|---|---|
| RELIANCE | Jun-26 | 593 KB | 32 | 100,410 | 0 | custom: "Questioner (Name, Firm)" / "Company Speaker (Name)" / "Sh Name hh:mm:ss–hh:mm:ss (Segment)" |
| TCS | Sep-26 | 707 KB | 29 | 52,478 | 0 | "Name:" |
| HDFCBANK | Sep-26 | 469 KB | 17 | 54,627 | 0 | "Name:" + MANAGEMENT roster |
| ASIANPAINT | Jun-26 | 4,590 KB | 26 | 49,503 | 0 | "Name:" |
| DIXON | Jun-26 | 834 KB | 21 | 58,526 | 0 | "Name:" + MANAGEMENT/MODERATOR roster (Chorus Call) |
| KPITTECH | Jun-26 | 473 KB | 20 | 49,869 | 0 | "Name:" + MANAGEMENT/MODERATOR roster (Chorus Call) |

All downloads returned HTTP 200, taking 209–1,089 ms (plain session).
- **Cover letter:** each PDF starts with a company-secretary cover letter (1–2 pages) before the transcript.
- **Text quality:**
  - The TCS PDF has **26 broken-ligature glyphs** (`OƯicer` for "Officer", from a bad font map) plus 56 standard ligatures (`ﬁ`). Both are fixed with NFKC plus one glyph mapping. Without the fix, verbatim quotes and keyword search break.
  - Repeated page headers and footers (company, date, "Page x of y") interrupt speaker turns and are removed.
  - Line-wrap artefacts remain, e.g. "quarter- on-quarter" (DIXON).

## Speaker segmentation and roles (no LLM)
| symbol | turns | moderator | host | management | analyst | mgmt speakers | analyst speakers | words mgmt / analyst |
|---|---|---|---|---|---|---|---|---|
| RELIANCE | 65 | — | — | 36 | 29 | 11* | 8 | 14,703 / 1,630 |
| TCS | 101 | 14 | — | 48 | 39 | 5 | 11 | 5,185 / 2,307 |
| HDFCBANK | 75 | 14 | — | 39 | 22 | 4 | 8 | 6,765 / 1,700 |
| ASIANPAINT | 57 | 9 | — | 24 | 24 | 2 | 8 | 2,723 / 1,604 |
| DIXON | 124 | 15 | 1 | 62 | 46 | 2 | 10 | 5,911 / 2,558 |
| KPITTECH | 80 | 11 | 1 | 40 | 28 | 6* | 8 | 5,949 / 1,818 |

\* These counts include name variants of the same person (see below).

**Role rules, in priority order:**
1. An explicit label (RELIANCE's "Questioner" / "Company Speaker").
2. The transcript's MODERATOR: block → host (the broker running the call).
3. Named by the moderator within about 100 characters after "question" (full name, or first-name prefix plus surname) → analyst.
4. Everyone else → management.

**Accuracy evidence:**
- **Roster cross-check:** every name in the transcript's own MANAGEMENT: roster was labelled management (HDFCBANK 4/4, DIXON 2/2, KPITTECH 5/5).
- **Manual spot checks** of names that fell through to management by default:
  - TCS "Sudeep Kunnumal": the transcript introduces him as Chief HR Officer, so **correct**.
  - ASIANPAINT "Jaykumar Doshi": he was introduced as "Mr. Jay Doshi from Kotak", so he was **wrong** under the first rule set.
  - A surname-only fix then mislabelled TCS's IR head "Nehal Shah", because analyst "Sandeep Shah" shares the surname. The final rule (first-name prefix plus surname) labels both correctly.
- **Known open issue: name variants.** "V Srikanth / V. Srikanth / V Shrikanth" (RELIANCE CFO) and "Priya / Priyamvada Hardikar" (KPIT CFO). Attributing quotes per person needs fuzzy name merging against the roster.

## Verbatim receipts: forward-looking management sentences containing a number
These were found with a regex for forward-looking language plus at least one digit. They are quoted exactly as extracted, with page numbers, and nothing has been interpreted from them.

| symbol | page | speaker | quote |
|---|---|---|---|
| ASIANPAINT | 20 | Amit Syngle | "We are still garnering around the guidance of 18-20% of our PBDIT margins holds." |
| DIXON | 3 | Atul Lall | "We expect the JV to commence operations and start reflecting in our revenues from Q3 of the current fiscal." |
| KPITTECH | 3 | Kishor Patil | "During the outlook, we have just mentioned that H2 will be better than H1, and we will return to growth in H2 by Q4, …" |
| RELIANCE | 18 | Sanjay Barman Roy | "But again, we expect this to trend upwards and go towards $9.9 in the second half." |
| HDFCBANK | 9 | Kaizad Bharucha | "And therefore, I think going forward, across the next 2 quarters, you will see that change coming through as we also grow the volumes in retail and MSME." |

These are the raw material for the promise ledger:
- A **checkable claim** (ASIANPAINT's 18–20% PBDIT margin, which XBRL from spike 05 can test).
- A **dated milestone** (DIXON's JV revenue from Q3).
- A **directional promise** (KPIT returning to growth by Q4).

## What failed or is weak
- **Regex precision for guidance is low:**
  - Some hits aren't promises. KPIT p20: "I have not seen the numbers we will analyze and tell you…". ASIANPAINT p22 is a retrospective comment.
  - The **TCS transcript produced 0 hits**. Whether that's genuine (no numeric forward-looking statement) or a recall miss wasn't checked.
  - **Recommendation:** regex or keywords as a cheap candidate filter (5–20 sentences per call), then an LLM classifies and structures **only those candidates** into {metric, target, deadline, speaker, page, verbatim}. That keeps model input at roughly 1–2k tokens per call, against roughly 15–35k for a whole transcript.
- **Layout dependence:** 2 distinct layouts across 6 companies (Chorus-Call style "Name:" vs Reliance's custom labels). More will appear across the 15–20-stock portfolio. Each new layout is a small pattern addition; unmatched layouts should produce "0 turns" and alert, never be silently skipped.
- **Discovery depends on the subject containing "transcript".** ASIANPAINT Mar-26 is a probable miss of this kind.

## Missing fields
- **No structured call metadata from NSE:** the call date and time appear only in the PDF text, the cover letter or the subject.
- **No audio:** RELIANCE files a separate "audio recording" notice; audio is on company websites only.
- **No analyst firm,** except in RELIANCE's format and the moderator's introductions ("from Kotak").

## Cost
- **Discovery:** 1 announcements request per symbol per window. In production, the daily market-wide feed from spike 02 already contains these filings, so discovery costs **0 extra requests**.
- **Download:** about 0.5–4.6 MB per transcript, 1 request. For 20 stocks × 4 quarters ≈ 80 files per year, about 60 MB.
- **Processing:** pymupdf plus regex in milliseconds, 0 tokens. The only LLM step is classifying candidate sentences (see above).

## Fallback
- **Company IR pages:** the cover letters give the URLs, e.g. `dixoninfo.com/financial-performance` and `kpit.com/investor-financials`. That would need a per-company mapping.
- **BSE filings:** deferred under the NSE-only decision.
- **Audio plus speech-to-text:** heavy, and only if a transcript is never filed.

## Terms-of-use and stability risk
- Same announcements API as spike 02 (undocumented, cookie-gated), with PDFs on static `nsearchives` URLs.
- Transcripts are company-authored disclosures under SEBI LODR Reg 30/46, so they are primary sources.

## Proposed signatures
```python
def find_transcripts(symbol: str, start: date, end: date) -> list[dict]:
    """Earnings-call transcripts only (AGM/other excluded), one per results quarter (latest filing wins).
    -> [{"symbol", "quarter_end", "filed_at", "pdf_url", "subject", "seq_id"}]"""

def parse_transcript(pdf: bytes) -> dict:
    """-> {"turns": [{"speaker", "role": moderator|host|management|analyst, "page", "text"}],
          "management": [...], "analysts": [...], "layout": "chorus"|"ril"|..., "warnings": [...]}
    Text is NFKC-normalised with headers/footers stripped; 'turns' empty + warning if layout unknown."""

def guidance_candidates(parsed: dict) -> list[dict]:
    """Management sentences with forward-looking language and a number: {"speaker", "page", "quote"}.
    Verbatim; to be classified downstream, never paraphrased here."""
```
