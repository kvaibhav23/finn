"""Spike 01: map any NSE symbol -> name, series, ISIN.

Source: NSE EQUITY_L.csv (all listed mainboard equities, with ISIN).
BSE scrip-code mapping is deferred: api.bseindia.com returned 403 to plain
requests (see REPORT.md), and the project decided to go NSE-only for now.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd

from common import fetch, log_summary, make_session
from tickers import SAMPLE

NSE_EQUITY_L = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def load_nse_master() -> pd.DataFrame | None:
    # Try without cookies first, to learn whether nsearchives needs them.
    for site in ("plain", "nse"):
        f = fetch(make_session(site), NSE_EQUITY_L)
        if f.ok and f.content.lstrip().startswith(b"SYMBOL"):
            print(f"EQUITY_L via session={site!r}: {len(f.content):,} bytes, cached={f.cached}")
            df = pd.read_csv(io.BytesIO(f.content))
            df.columns = [c.strip() for c in df.columns]
            return df.apply(lambda s: s.str.strip() if s.dtype == object else s)
        print(f"EQUITY_L via session={site!r} failed: {f.status} {f.error} {(f.content or b'')[:120]!r}")
    return None


def resolve_symbol(master: pd.DataFrame, nse_symbol: str) -> dict:
    row = master.loc[master["SYMBOL"] == nse_symbol.upper()]
    if row.empty:
        raise KeyError(nse_symbol)
    r = row.iloc[0]
    return {"symbol": r["SYMBOL"], "name": r["NAME OF COMPANY"], "series": r["SERIES"],
            "isin": r["ISIN NUMBER"], "listed": r["DATE OF LISTING"]}


def main():
    master = load_nse_master()
    if master is None:
        print("FAIL: NSE master did not load.\n" + log_summary())
        return

    print(f"rows={len(master):,} columns={list(master.columns)}")
    print(f"series={master['SERIES'].value_counts().to_dict()}")
    print(f"duplicate symbols={master['SYMBOL'].duplicated().sum()} "
          f"duplicate ISINs={master['ISIN NUMBER'].duplicated().sum()} "
          f"blank ISINs={master['ISIN NUMBER'].isna().sum()}")

    print("\nSample tickers:")
    for sym in SAMPLE:
        try:
            print(" ", resolve_symbol(master, sym))
        except KeyError:
            print(f"  {sym}: NOT IN NSE MASTER")

    for bad in ("NOTATICKER",):
        try:
            resolve_symbol(master, bad)
        except KeyError:
            print(f"  {bad}: KeyError (as expected)")

    print("\n" + log_summary())


if __name__ == "__main__":
    main()
