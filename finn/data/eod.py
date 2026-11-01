"""End-of-day prices for the whole market from NSE's daily files (spike 04).

UDiFF bhavcopy is published ~16:33 IST; sec_bhavdata_full (delivery %) ~23:55 IST.
Trap 8: a 404 for a past date means "no trading session" (cached, returns None); a 404 for
today means "not published yet" (not cached, raises NotYetPublished so the caller retries).
"""
from __future__ import annotations

import io
import zipfile
from datetime import date

import pandas as pd

from . import http

UDIFF = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
FULL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv"
SERIES = ("EQ", "BE", "BZ", "SM", "ST")


class NotYetPublished(RuntimeError):
    pass


def parse_udiff(zip_bytes: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        raw = pd.read_csv(z.open(z.namelist()[0]))
    raw = raw[raw["SctySrs"].isin(SERIES)]
    return pd.DataFrame({
        "symbol": raw["TckrSymb"], "isin": raw["ISIN"], "series": raw["SctySrs"],
        "open": raw["OpnPric"], "high": raw["HghPric"], "low": raw["LwPric"], "close": raw["ClsPric"],
        "last": raw["LastPric"], "prev_close": raw["PrvsClsgPric"], "volume": raw["TtlTradgVol"],
        "value": raw["TtlTrfVal"], "trades": raw["TtlNbOfTxsExctd"],
        "date": pd.to_datetime(raw["TradDt"]).dt.date,
    }).reset_index(drop=True)


def parse_full(csv_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(csv_bytes), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda s: s.str.strip() if s.dtype == object else s)
    out = df[["SYMBOL", "SERIES", "DELIV_QTY", "DELIV_PER"]].rename(columns={
        "SYMBOL": "symbol", "SERIES": "series", "DELIV_QTY": "deliv_qty", "DELIV_PER": "deliv_pct"})
    for c in ("deliv_qty", "deliv_pct"):
        out[c] = pd.to_numeric(out[c], errors="coerce")  # '-' for non-delivery series
    return out


def _fetch_daily_file(url: str, day: date, c: http.Client) -> bytes | None:
    past = day < c.today()
    r = c.get(url, policy="permanent", cache_404=past)  # once published, a day's file never changes
    if r.ok:
        return r.content
    if r.status == 404:
        if past:
            return None
        raise NotYetPublished(f"{url} not published yet (today {c.today()})")
    raise http.FetchError(f"{r.status} {r.error} {url}")


def get_eod(day: date, with_delivery: bool = False, client: http.Client | None = None) -> pd.DataFrame | None:
    """Whole market for one trading day; None if `day` (in the past) had no session."""
    c = client or http.client()
    if day > c.today():
        raise NotYetPublished(f"{day} is in the future")
    z = _fetch_daily_file(UDIFF.format(d=day), day, c)
    if z is None:
        return None
    df = parse_udiff(z)
    if with_delivery:
        full = _fetch_daily_file(FULL.format(d=day), day, c)
        if full is None:
            raise http.FetchError(f"bhavcopy exists for {day} but delivery file is missing")
        df = df.merge(parse_full(full), on=["symbol", "series"], how="left")
    df.attrs["source_url"] = UDIFF.format(d=day)
    return df
