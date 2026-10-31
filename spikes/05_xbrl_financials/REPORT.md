# Spike 05: quarterly financials from XBRL (no PDFs, no LLM)

**Verdict: PASS.**
- 24/24 latest-quarter XBRL files (6 tickers × 4 quarters, consolidated) downloaded and parsed.
- Covers both the Ind-AS and Banking taxonomies, and both the current and legacy formats.
- 2/2 spot-checked values appear verbatim in the results PDF.
- History runs from 2005 to Sep 2026 for the large caps.

Run: `python spikes/05_xbrl_financials/run.py`. First live run: 2026-11-01 ~01:57 IST. The re-run made 0 live requests.

## Key finding: NSE has two filing listings, split at Dec 2024
| listing | endpoint | covers | XBRL file prefix |
|---|---|---|---|
| Legacy financial results | `GET /api/corporates-financial-results?index=equities&period=Quarterly&symbol=X` | 2005-03 → **2024-12** (stops there) | `INDAS_…`, `BANKING_…` |
| SEBI Integrated Filing (Financials) | `GET /api/integrated-filing-results?index=equities&symbol=X&type=Integrated Filing- Financials&page=1&size=20` | **2025-03 → 2026-09** (current) | `INTEGRATED_FILING_INDAS_…`, `INTEGRATED_FILING_BANKING_…` |

- **Without its `type` parameter, the integrated endpoint mixes in Governance filings.**
- Both listings return one row per quarter × {Consolidated, Standalone}, with an `xbrl` URL on `nsearchives` (plain session, no cookies).
- The integrated listing is paginated (`totalCount`). It's 14–18 rows per company today, so `size=20` will overflow within about a year.
- Endpoint discovered via [nse-xbrl on PyPI](https://pypi.org/project/nse-xbrl/) and an nsepython pull request. Neither is official documentation.

## Coverage (filings listed)
| symbol | legacy | integrated |
|---|---|---|
| RELIANCE | 2005-03 → 2024-12 (130) | 2025-03 → 2026-09 (14) |
| TCS | 2005-03 → 2024-12 (162) | 2025-03 → 2026-09 (14) |
| HDFCBANK | 2005-03 → 2024-12 (103) | 2025-03 → 2026-09 (14) |
| ASIANPAINT | 2005-03 → 2024-12 (164) | 2025-03 → 2026-09 (18) |
| DIXON | 2017-06 → 2024-12 (60) | 2025-03 → 2026-09 (16) |
| KPITTECH | 2019-03 → 2024-12 (47) | 2025-03 → 2026-09 (14) |

## Sample output: quarterly, consolidated, ₹ crore (EPS in ₹)
| symbol | quarter | revenue | interest earned | total income | PBT | PAT | PAT (owners) | basic EPS |
|---|---|---|---|---|---|---|---|---|
| RELIANCE | 2026-09-30 | 332,861 | — | 338,654 | 38,613 | 29,550 | 25,548 | 18.88 |
| TCS | 2026-09-30 | 73,188 | — | 74,525 | 18,638 | 13,934 | 13,884 | 38.37 |
| HDFCBANK | 2026-09-30 | — | 95,132 | 129,359 | 27,825 | 20,700 | 20,700 | 13.43 |
| ASIANPAINT | 2026-09-30 | 9,977 | — | 10,224 | 1,436 | 1,085 | 1,068 | 11.14 |
| DIXON | 2026-09-30 | 21,794 | — | 21,862 | 530 | 411 | 344 | 67.44 |
| KPITTECH | 2026-09-30 | 1,691 | — | 1,699 | 184 | 121 | 121 | 4.43 |

The full 24-row table is in the `run.py` output. Each value maps to one XBRL tag; the tags are listed in `LINE_ITEMS` in `run.py`.

**Spot check (mechanical string search, no interpretation):** TCS Q2 FY27 results PDF (`TCS_CORPCS_08102026153124_Post_BM_SE_Letter_fin.pdf`, 22 pages).
- XBRL `RevenueFromOperations` = 731,880,000,000 → "73,188" **found**.
- XBRL `ProfitLossForPeriod` = 139,340,000,000 → "13,934" **found**.

## HTTP status and latency
| call | n | status | latency | size |
|---|---|---|---|---|
| integrated listing | 6 | 200 | 148–426 ms | about 10 KB |
| legacy listing | 6 | 200 | 291–579 ms | up to 125 KB |
| XBRL, consolidated, integrated | 24 | 200 | 115–619 ms | 15–107 KB |
| XBRL, legacy | 2 | 200 | 86–355 ms | 53–67 KB |
| results PDF (spot check) | 1 | 200 | 1,061 ms | — |
| NSE home-page warm-up | 1 | 403 (cookies still set) | 342 ms | — |

## Traps found (each is handled in `parse_xbrl`)
1. **Legacy files mislabel the YTD context.**
   - The `FourD` context declares the quarter's dates (2024-10-01 → 2024-12-31), but holds **9-month YTD** values: TCS revenue 1,90,845 vs 63,973 for the quarter.
   - The filing's own `DateOfStartOfReportingPeriod` fact for `FourD` reads 2024-04-01.
   - **Fix:** contexts are validated against that fact.
   - **Consequence:** never select contexts by declared dates alone.
2. **Two taxonomies.** Banks use different tags:
   - `InterestEarned`, `InterestExpended`, `OperatingExpenses`, `ProvisionsOtherThanTaxAndContingencies`, `ProfitLossForThePeriod`, `ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates`.
   - There is no `RevenueFromOperations`, `FinanceCosts` or D&A.
   - Line items need a per-taxonomy map, not one tag list.
3. **Zero means "not reported".** HDFCBANK's consolidated filing tags `PercentageOfGrossNpa`, `GrossNonPerformingAssets`, `CET1Ratio` and `ReturnOnAssets` as `0`. Asset quality lives in the standalone filing. These zeros are treated as missing, never shown.
4. **EPS series breaks.** HDFCBANK basic EPS was 23.11 (Dec-2024), then 12.88–13.43 (2025-26), while PAT rose from 18,340 to 20,700 cr.
   - That's consistent with a change in share count; check the cause against corporate actions.
   - **Any per-share trend in the promise ledger must be adjusted for corporate actions, or compared on absolute PAT.**
5. **Rounding.** Values are in INR with `decimals="-7"`, i.e. rounded to ₹1 crore. The integrated format also states `LevelOfRounding` (e.g. "Crores"); the legacy format doesn't.
6. **Standalone files can be about 3.4 MB** (TCS) against about 100 KB consolidated. Download consolidated by default.

## Missing fields
- **EBITDA:** no tag. It's derivable deterministically as PBT + finance costs + D&A − other income, and must be labelled as derived.
- **Ind-AS files:** no segment-wise table extracted yet. Segment tags exist (`SegmentRevenue`, `SegmentProfitBeforeTax` …) with dimension contexts, but they're out of scope here.
- **Bank asset quality** (GNPA %, CET1) is missing from consolidated filings. It needs the standalone file, which wasn't fetched in this spike.
- **KPIs management talks about** (order book, deal TCV, volume growth, margins by segment) are **not in XBRL**. They exist only in presentations and transcripts (spikes 06/07). This is the main limit for the promise ledger: XBRL gives the P&L, not the operating KPIs.
- **Useful extras present:**
  - board-meeting date (`DateOfBoardMeetingWhenFinancialResultsWereApproved`);
  - audited/unaudited flag;
  - `type_Sub` (Original vs revised) in the listing;
  - an iXBRL HTML version of each filing (`ixbrl` field).

## Cost
- **Quarterly refresh for 20 stocks:** 20 × (1 listing + 1 XBRL) = **about 40 requests per quarter**, about 2 MB.
- **3-year backfill (12 quarters):** 20 × (2 listings + 12 XBRL) = about 280 requests once, about 10–15 MB, cached forever. Past filings are immutable, apart from revisions, which arrive as new rows.
- **Zero LLM tokens.**

## Fallback
- **Same filings, other formats:** the iXBRL HTML (`ixbrl` field) of the same filing, or the results PDF tables (pdfplumber). The PDF route only for display, never as a source of numbers.
- **Untested:** the BSE XBRL listing (deferred under the NSE-only decision), and `jugaad-xbrl` / `nse-xbrl` as parser references. They're not added as dependencies; the lxml parser here is about 60 lines.

## Terms-of-use and stability risk
- **Both listings are undocumented NSE APIs.** The format already changed once (the Integrated Filing switch in 2025), so the listing layer must handle both.
- **The XBRL taxonomy is SEBI's.** It's stable and versioned in the namespace (`2025-01-31`, `2026-01-31`), so parse by element local name.
- **The XBRL files** live on static `nsearchives` URLs.

## Proposed signature
```python
def get_quarterly_financials(symbol: str, n_quarters: int = 12,
                             basis: str = "Consolidated") -> pd.DataFrame:
    """One row per quarter-end. Columns: qe, basis, source (legacy|integrated), audited,
    board_meeting, taxonomy (indas|banking), revenue | interest_earned, other_income,
    total_income, total_expenses, pbt, tax, pat, pat_owners, eps_basic, ...  (INR, as tagged)
    + xbrl_url and xbrl_tag per value for receipts. Missing -> NaN, never 0-filled."""
```
