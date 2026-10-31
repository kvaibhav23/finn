"""Spike 02: NSE corporate announcements for a portfolio over a date window.

Two access patterns:
  A. per symbol:   /api/corporate-announcements?index=equities&symbol=X&from_date&to_date
  B. whole market: same endpoint with no symbol, one day at a time (filter locally)
Plus: download a couple of attachment PDFs.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd

from common import fetch, log_summary, make_session
from tickers import SAMPLE

API = "https://www.nseindia.com/api/corporate-announcements"
FROM, TO = "01-10-2026", "31-10-2026"     # fixed window -> stable cache keys
MARKET_DAYS = ["30-10-2026", "31-10-2026"]  # whole-market sample days


def get_json(params: dict):
    f = fetch(make_session("nse"), API, params=params)
    if not f.ok:
        print(f"  FAIL {f.status} {f.error} body={(f.content or b'')[:150]!r}")
        return None
    try:
        return f.json()
    except ValueError:
        print(f"  NOT JSON ({f.content_type}): {f.content[:150]!r}")
        return None


def main():
    s = make_session("nse")

    print("== A. per symbol ==")
    frames = []
    for sym in SAMPLE:
        data = get_json({"index": "equities", "symbol": sym, "from_date": FROM, "to_date": TO})
        if data is None:
            break  # first failure: stop hammering, report it
        rows = data if isinstance(data, list) else data.get("data", [])
        print(f"  {sym}: {len(rows)} announcements")
        frames.append(pd.DataFrame(rows))
    per_sym = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    print(f"  cookies after warm-up: {sorted(s.cookies.keys())}")

    if per_sym.empty:
        print("\nNo data from pattern A; skipping the rest.\n" + log_summary())
        return

    print(f"\nfields: {list(per_sym.columns)}")
    null_rate = per_sym.isna().mean().round(2)
    print(f"null rate (non-zero): {null_rate[null_rate > 0].to_dict()}")
    if "desc" in per_sym:
        print("\ncategory ('desc') counts:")
        print(per_sym["desc"].value_counts().to_string())
    show = [c for c in ["symbol", "desc", "an_dt", "exchdisstime", "attchmntText", "attchmntFile"] if c in per_sym]
    print("\nsample rows:")
    with pd.option_context("display.max_colwidth", 70, "display.width", 250):
        print(per_sym[show].head(8).to_string(index=False))

    print("\n== B. whole market, one day per call ==")
    for day in MARKET_DAYS:
        data = get_json({"index": "equities", "from_date": day, "to_date": day})
        if data is None:
            break
        rows = data if isinstance(data, list) else data.get("data", [])
        mine = [r for r in rows if r.get("symbol") in SAMPLE]
        print(f"  {day}: {len(rows)} announcements market-wide, {len(mine)} for sample "
              f"({Counter(r.get('symbol') for r in mine)})")
        # Cross-check: does the market-wide feed contain what per-symbol calls returned for that day?
        if "an_dt" in per_sym:
            d = pd.to_datetime(day, format="%d-%m-%Y").strftime("%d-%b-%Y")
            expected = per_sym[per_sym["an_dt"].astype(str).str.startswith(d)]
            got = {(r.get("symbol"), r.get("an_dt")) for r in mine}
            missing = [(a, b) for a, b in zip(expected["symbol"], expected["an_dt"]) if (a, b) not in got]
            print(f"    per-symbol rows that day: {len(expected)}, missing from market feed: {len(missing)}")

    print("\n== C. attachments ==")
    if "attchmntFile" in per_sym:
        atts = per_sym["attchmntFile"].dropna()
        atts = atts[atts.str.startswith("http")]
        print(f"  {len(atts)}/{len(per_sym)} rows have an attachment URL; "
              f"extensions={Counter(Path(u.split('?')[0]).suffix.lower() for u in atts)}")
        for url in atts.head(2):
            f = fetch(make_session("plain"), url)
            head = (f.content or b"")[:5]
            print(f"  {f.status} {f.content_type} {len(f.content or b''):,} bytes "
                  f"starts={head!r} -> {f.path.name if f.path else f.error}")

    print("\n" + log_summary())


if __name__ == "__main__":
    main()
