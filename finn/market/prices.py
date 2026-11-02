"""One year of end-of-day prices per company, from NSE's daily market files (finn/data/eod.py).

Each day's file covers the whole market, so many companies are read in one pass and every file is
downloaded once (cached in data/raw). Prices before a split or bonus are divided by its share-count
factor, so the line has no false cliffs. Delivery % is read only for recent sessions (one more file a day).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import pandas as pd

from finn.data import eod, http
from finn.data.corporate_actions import factor_after

NIFTY = "Nifty 50"
DAYS = 372              # a year plus a week, so "a year ago" always has a session
DELIVERY_DAYS = 90      # calendar days with delivery % (~60 sessions)
SERIES_PREF = {"EQ": 0, "BE": 1, "BZ": 2}
SOURCE = "NSE end-of-day bhavcopy"


def weekdays(end: date, days: int) -> list[date]:
    d, out = end - timedelta(days=days), []
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _day(eod_fn: Callable, d: date, delivery: bool) -> pd.DataFrame | None:
    try:
        return eod_fn(d, delivery)
    except eod.NotYetPublished:
        return None
    except http.FetchError:
        if not delivery:
            raise
        return eod_fn(d, False)        # bhavcopy out, delivery file not yet: prices without it


def history(symbols: list[str], end: date, days: int = DAYS, delivery_days: int = DELIVERY_DAYS,
            client: http.Client | None = None, eod_fn: Callable | None = None,
            index_fn: Callable | None = None) -> tuple[dict[str, list[dict]], list[dict]]:
    """-> ({symbol: [{date, open, high, low, close, volume, deliv_pct}, ...]}, nifty [{date, close}]), oldest first."""
    c = client or http.client()
    eod_fn = eod_fn or (lambda d, delivery: eod.get_eod(d, with_delivery=delivery, client=c))
    index_fn = index_fn or (lambda d: eod.get_index_close(d, client=c))
    wanted, rows, nifty = set(symbols), {s: [] for s in symbols}, []
    deliv_from = end - timedelta(days=delivery_days)
    for d in weekdays(end, days):
        df = _day(eod_fn, d, d >= deliv_from)
        if df is None:
            continue
        df = df[df["symbol"].isin(wanted) & df["series"].isin(SERIES_PREF)]
        df = df.assign(_p=df["series"].map(SERIES_PREF)).sort_values("_p").drop_duplicates("symbol")
        for r in df.to_dict("records"):
            dp = r.get("deliv_pct")
            rows[r["symbol"]].append({"date": d, "open": float(r["open"]), "high": float(r["high"]),
                                      "low": float(r["low"]), "close": float(r["close"]),
                                      "volume": int(r["volume"]),
                                      "deliv_pct": float(dp) if dp is not None and pd.notna(dp) else None})
        try:
            idx = index_fn(d)
        except (eod.NotYetPublished, http.FetchError):
            idx = None
        if idx and NIFTY in idx:
            nifty.append({"date": d, "close": idx[NIFTY]})
    return rows, nifty


def adjust(rows: list[dict], actions: pd.DataFrame | None) -> tuple[list[dict], list[str]]:
    """Express past prices in today's share terms: price / factor, volume x factor, for days before each
    split or bonus ex-date. Returns (rows, subjects of the actions applied)."""
    if actions is None or actions.empty:
        return rows, []
    out, applied = [], set()
    for r in rows:
        f, why = factor_after(actions, r["date"])
        if f == 1.0:
            out.append(r)
            continue
        applied.update(why)
        out.append(r | {k: r[k] / f for k in ("open", "high", "low", "close")} | {"volume": int(r["volume"] * f)})
    return out, sorted(applied)
