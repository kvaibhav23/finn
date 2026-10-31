# Spike 01: symbol master (NSE symbol → name, series, ISIN)

**Verdict: PASS (NSE-only).** The BSE scrip-code mapping is deferred (see "What failed").

Run: `python spikes/01_symbol_master/run.py`. First live run: 2026-11-01 01:44 IST. The re-run was served entirely from cache (0 live requests).

## What worked
- **NSE `EQUITY_L.csv`** (`https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv`)
  - HTTP 200, 617 ms, 185,023 bytes, `text/csv`. **One request covers the whole universe.**
  - **No cookie warm-up needed.** It worked from a plain session with a browser User-Agent.
  - 2,620 rows. Series: EQ 2,357, BE 230, BZ 33.
  - 0 duplicate symbols, 0 duplicate ISINs, 0 blank ISINs.
  - All 6 sample tickers resolved, and an unknown symbol raises `KeyError`.

## Sample output
| SYMBOL | NAME | SERIES | ISIN | LISTED |
|---|---|---|---|---|
| RELIANCE | Reliance Industries Limited | EQ | INE002A01018 | 29-NOV-1995 |
| TCS | Tata Consultancy Services Limited | EQ | INE467B01029 | 25-AUG-2004 |
| HDFCBANK | HDFC Bank Limited | EQ | INE040A01034 | 08-NOV-1995 |
| ASIANPAINT | Asian Paints Limited | EQ | INE021A01026 | 31-MAY-1995 |
| DIXON | Dixon Technologies (India) Limited | EQ | INE935N01020 | 18-SEP-2017 |
| KPITTECH | KPIT Technologies Limited | EQ | INE04I401011 | 22-APR-2019 |

## What failed
- **BSE `ListofScripData`** (`api.bseindia.com/BseIndiaAPI/api/ListofScripData/w`) returned **HTTP 403 "Access Denied"**, an Akamai edge block. Latency 516 ms, 420-byte block page.
- **Diagnosis:**
  - The same endpoint returned HTTP 200 through the `bse` package with its built-in headers (702 Group-A securities, 1,213 ms; DIXON → 540699 via its lookup).
  - The block depends on the User-Agent string. Header probing stopped there, because tuning headers to pass a bot check is circumvention.
- **Decision (2026-11-01): go NSE-only for now.** BSE is a noted fallback, not a dependency. `run.py` no longer calls BSE.

## Missing fields
- No BSE scrip code, sector, industry or market cap.
- **SME-board symbols (SM/ST series) are not in this file.** FINN's "any NSE ticker" means mainboard only, until a source for SME symbols is found.

## Fallback
- **If NSE archives fail:** a static ISIN list from NSDL, or NSE's equity quote API (cookie-gated, tested in spike 02).
- **If a BSE code is ever needed:** the `bse` package's `getScripCode()`. It worked in a one-off test, but BSE sits behind bot protection.

## Terms-of-use and stability risk
- **NSE archives:** a static CSV, low risk. The file moved hosts before (to `nsearchives.`), so keep the URL in one constant.
- **Refresh cadence:** about once a day is plenty, since new listings are rare. Because the cache never re-downloads, production needs a cache key that includes the date (for example `?d=YYYYMMDD`), or a separate "daily file" policy. This is a design note for the summary.

## Proposed signature
```python
def resolve_symbol(nse_symbol: str) -> dict:
    """-> {"symbol", "name", "series", "isin", "listed"}; raises KeyError if not a listed NSE mainboard equity."""
```
