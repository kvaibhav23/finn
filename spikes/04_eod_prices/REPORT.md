# Spike 04: end-of-day price, volume and delivery %

**Verdict: PASS.** The NSE daily price files are the primary source, and yfinance is the fallback. All three sources agree exactly on close and volume (18/18 symbol-days).

Run: `python spikes/04_eod_prices/run.py`. First live run: 2026-11-01 ~01:53 IST. The re-run made 0 live requests (yfinance's result is cached as a CSV too).
Dates: 28, 29 and 30 Oct 2026 (Wed–Fri), plus Sat 31 Oct as a non-trading control.

## What worked
- **NSE UDiFF CM bhavcopy:** `nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`
  - About 205 KB zip, 3,641–3,697 rows per day, the **whole market in one file**. 122–686 ms, plain session, no cookies.
  - Series: EQ 2,711, SM 373, BE 211, ST 77, GS 47, GB 41, BZ 32 and others. **SME (SM/ST) is included here**, even though spike 01's `EQUITY_L.csv` lacks it.
  - Has OHLC, close, last, **previous close**, volume, traded value, trade count and ISIN.
- **NSE `sec_bhavdata_full`:** `nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv`
  - About 396 KB csv, 3,503–3,535 rows, 122–126 ms.
  - Adds **DELIV_QTY / DELIV_PER** (delivery %), plus average price and turnover.
- **yfinance** (`RELIANCE.NS` and so on, `auto_adjust=False`): one `download()` for 6 tickers took 5,222 ms.
  - Close and volume were identical to NSE, so Yahoo is serving NSE's official close and EQ-series volume.

## Publication time (from the `Last-Modified` header; this matters for alert timing)
| file | Last-Modified (GMT) | IST | relative to the 15:30 IST close |
|---|---|---|---|
| UDiFF bhavcopy | 11:03:02 on all 3 days | **16:33** | about 1 h after close |
| sec_bhavdata_full | 18:25:35–37 | **23:55** | about 8.5 h after close |

**Price and volume alerts can fire at about 16:35 IST. Delivery-% signals aren't available until about midnight.**

## Sample output (EQ series; u = UDiFF, f = full, yf = yfinance)
| date | symbol | u_close | u_prev | u_vol | f_close | f_vol | deliv % | yf_close | yf_vol |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-28 | RELIANCE | 1158.00 | 1196.2 | 21,866,598 | 1158.00 | 21,866,598 | 45.27 | 1158.00 | 21,866,598 |
| 2026-10-29 | ASIANPAINT | 2302.00 | 2284.6 | 2,521,129 | 2302.00 | 2,521,129 | 30.08 | 2302.00 | 2,521,129 |
| 2026-10-30 | DIXON | 11000.00 | 11488.0 | 521,838 | 11000.00 | 521,838 | 33.70 | 11000.00 | 521,838 |

All 18 rows match on all 4 comparisons. The yf/NSE volume ratio is exactly 1.0. The full table is in the `run.py` output.

## HTTP status and latency
| call | status | latency | bytes |
|---|---|---|---|
| UDiFF × 3 days | 200 | 147–686 ms | 203–206 KB |
| full × 3 days | 200 | 122–126 ms | 396–399 KB |
| UDiFF, Sat 31-Oct | **404** | 139 ms | 3.8 KB HTML |
| full, Sat 31-Oct | **404** | 139 ms | 3.9 KB HTML |
| yfinance, 6 tickers × 3 days | n/a (library) | 5,222 ms | — |

**A non-trading day returns a clean 404.** That makes a usable "no session today" signal: these 404s are cached, because a past date's file will never appear. **Today's** 404 before 16:33 means "not yet published", so it must not be cached.

## What failed
Nothing in scope.

## Notes
- yfinance prints `Pandas4Warning` deprecation noise (from inside yfinance, harmless).
- Windows are fixed to past dates, so these results don't show the edge cases around the publish moment.

## Missing fields
- No corporate-action adjustment in any NSE file. The prices are raw.
- `PrvsClsgPric` is NSE's previous close, which **NSE adjusts on ex-dates**. That makes it the right base for a "% change today" alert, and yesterday's raw close is the wrong one.
- No 52-week high/low and no averages. These have to be computed from history.
- yfinance: no delivery %.

## Cost (20-stock portfolio, per day)
| approach | requests/day | bytes/day | covers |
|---|---|---|---|
| UDiFF bhavcopy | **1** | about 205 KB | every NSE stock, every user |
| + sec_bhavdata_full | +1 | +about 396 KB | adds delivery % |
| yfinance | 1 batched call (about 5 s), library-managed | small | only the tickers asked for |

The bhavcopy cost is flat, whatever the number of users or portfolios. A 1-year history for alerts (moving averages, volume spikes) is about 250 files, roughly 51 MB zipped, fetched once and cached forever.

## Fallback
- **Primary for alerts:** UDiFF bhavcopy.
- **Delivery %:** `sec_bhavdata_full` (late).
- **Fallback:** yfinance. It matched exactly, but:
  - it's a scraper of an unofficial Yahoo API;
  - it pulls in `curl_cffi`, which impersonates a browser's TLS fingerprint;
  - it can't route through our cache or rate limiter.

  That makes it acceptable as a fallback, not as the foundation.
- **BSE bhavcopy:** deferred under the NSE-only decision.

## Terms-of-use and stability risk
- NSE archive files are public and static, and they've been the industry-standard EOD source for years. The format changed once (to UDiFF in July 2024), so keep the parser isolated.
- yfinance: see "Fallback".

## Proposed signature
```python
def get_eod(day: date, with_delivery: bool = False) -> pd.DataFrame | None:
    """Whole market for one trading day, EQ/BE/SM/ST series.
    Columns: symbol, isin, series, open, high, low, close, last, prev_close, volume, value, trades
    (+ deliv_qty, deliv_pct). None if the day was not a trading day (404 on a past date)."""
```
