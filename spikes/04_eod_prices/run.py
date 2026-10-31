"""Spike 04: cheapest reliable end-of-day price / volume / delivery% source.

  1. NSE UDiFF CM bhavcopy (zip)       - whole market, one file per day
  2. NSE sec_bhavdata_full (csv)        - whole market + delivery qty/%, one file per day
  3. yfinance (.NS)                     - per ticker, Yahoo
Compares close and volume for the sample on the same dates.
"""
import hashlib
import io
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd

from common import RAW, cached_meta, fetch, log_summary, make_session
from tickers import SAMPLE

DATES = [date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 30)]
NON_TRADING = date(2026, 10, 31)  # Saturday
UDIFF = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
FULL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv"


def load_udiff(d: date) -> pd.DataFrame | None:
    url = UDIFF.format(d=d)
    f = fetch(make_session("plain"), url, cache_404=True)
    if not f.ok:
        print(f"  UDiFF {d}: {f.status} {f.error}")
        return None
    with zipfile.ZipFile(io.BytesIO(f.content)) as z:
        name = z.namelist()[0]
        df = pd.read_csv(z.open(name))
    print(f"  UDiFF {d}: zip {len(f.content):,} B -> {name}, {len(df):,} rows, "
          f"Last-Modified={cached_meta(url)['last_modified']}")
    return df


def load_full(d: date) -> pd.DataFrame | None:
    url = FULL.format(d=d)
    f = fetch(make_session("plain"), url, cache_404=True)
    if not f.ok:
        print(f"  full  {d}: {f.status} {f.error}")
        return None
    df = pd.read_csv(io.BytesIO(f.content), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda s: s.str.strip() if s.dtype == object else s)
    print(f"  full  {d}: {len(f.content):,} B, {len(df):,} rows, "
          f"Last-Modified={cached_meta(url)['last_modified']}")
    return df


def load_yf(symbols: list[str], start: date, end: date) -> pd.DataFrame:
    """yfinance does its own HTTP; cache its result keyed by the call's arguments."""
    key_src = f"yfinance:download:{','.join(symbols)}:{start}:{end}:auto_adjust=False"
    path = RAW / f"{hashlib.sha256(key_src.encode()).hexdigest()[:20]}.csv"
    if path.exists():
        print(f"  yfinance: CACHE {path.name}")
        return pd.read_csv(path, parse_dates=["Date"])
    import yfinance as yf
    t0 = time.monotonic()
    raw = yf.download([f"{s}.NS" for s in symbols], start=start, end=end + timedelta(days=1),
                      auto_adjust=False, threads=False, progress=False, group_by="ticker")
    print(f"  yfinance: LIVE {int((time.monotonic() - t0) * 1000)} ms for {len(symbols)} tickers")
    out = (raw.stack(level=0, future_stack=True).rename_axis(["Date", "Ticker"]).reset_index())
    out["symbol"] = out["Ticker"].str.removesuffix(".NS")
    out.to_csv(path, index=False)
    return out


def main():
    print("== downloads ==")
    udiff = {d: load_udiff(d) for d in DATES}
    full = {d: load_full(d) for d in DATES}
    print(f"  non-trading day {NON_TRADING} (Saturday):")
    load_udiff(NON_TRADING)
    load_full(NON_TRADING)
    yfd = load_yf(SAMPLE, DATES[0], DATES[-1])

    d0 = udiff[DATES[0]]
    if d0 is not None:
        print(f"\nUDiFF columns: {list(d0.columns)}")
        print(f"UDiFF series mix: {d0['SctySrs'].value_counts().head(8).to_dict()}")
    f0 = full[DATES[0]]
    if f0 is not None:
        print(f"full columns: {list(f0.columns)}")

    print("\n== comparison (EQ series) ==")
    rows = []
    for d in DATES:
        u, f = udiff[d], full[d]
        for sym in SAMPLE:
            r = {"date": d, "symbol": sym}
            if u is not None:
                x = u[(u["TckrSymb"] == sym) & (u["SctySrs"] == "EQ")]
                if len(x):
                    x = x.iloc[0]
                    r |= {"u_close": x["ClsPric"], "u_prev": x["PrvsClsgPric"], "u_vol": x["TtlTradgVol"]}
            if f is not None:
                x = f[(f["SYMBOL"] == sym) & (f["SERIES"] == "EQ")]
                if len(x):
                    x = x.iloc[0]
                    r |= {"f_close": x["CLOSE_PRICE"], "f_vol": x["TTL_TRD_QNTY"], "deliv_pct": x["DELIV_PER"]}
            y = yfd[(yfd["symbol"] == sym) & (yfd["Date"].dt.date == d)]
            if len(y):
                r |= {"yf_close": round(float(y.iloc[0]["Close"]), 2), "yf_vol": y.iloc[0]["Volume"]}
            rows.append(r)
    cmp = pd.DataFrame(rows)
    for a, b in [("u_close", "f_close"), ("u_close", "yf_close"), ("u_vol", "f_vol"), ("u_vol", "yf_vol")]:
        if a in cmp and b in cmp:
            cmp[f"{a}=={b}"] = (cmp[a].astype(float) - cmp[b].astype(float)).abs() < 0.005
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(cmp.to_string(index=False))
    for c in [c for c in cmp.columns if "==" in c]:
        print(f"  {c}: {int(cmp[c].sum())}/{cmp[c].notna().sum()} match")
    if {"u_vol", "yf_vol"} <= set(cmp):
        ratio = (cmp["yf_vol"].astype(float) / cmp["u_vol"].astype(float)).round(4)
        print(f"  yf_vol / nse_vol ratios: {sorted(ratio.dropna().unique())[:10]}")

    print("\n" + log_summary())


if __name__ == "__main__":
    main()
