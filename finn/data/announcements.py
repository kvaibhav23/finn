"""NSE corporate announcements (spike 02): the filings feed behind the push digest and transcript discovery.

Trap 6: `hasXbrl` is True on every row (no signal) and (symbol, timestamp) is not unique,
so rows are deduplicated on `seq_id` only.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from . import http

API = "https://www.nseindia.com/api/corporate-announcements"
RENAME = {"seq_id": "seq_id", "symbol": "symbol", "sm_name": "name", "sm_isin": "isin",
          "smIndustry": "industry", "desc": "category", "attchmntText": "subject",
          "an_dt": "filed_at", "exchdisstime": "disseminated_at", "attchmntFile": "pdf_url",
          "attFileSize": "pdf_size"}
COLUMNS = list(RENAME.values())


def parse_announcements(content: bytes | list) -> pd.DataFrame:
    rows = json.loads(content) if isinstance(content, (bytes, str)) else content
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    df = df[[c for c in RENAME if c in df.columns]].rename(columns=RENAME)  # drops hasXbrl & always-null fields
    for col in ("filed_at", "disseminated_at"):
        df[col] = pd.to_datetime(df[col], format="%d-%b-%Y %H:%M:%S", errors="coerce")
    df["subject"] = df["subject"].fillna("").str.strip()
    return combine([df])


def combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate (e.g. overlapping windows) and dedupe on seq_id; newest first."""
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat(frames, ignore_index=True).drop_duplicates("seq_id", keep="last")
    return df.sort_values("filed_at", ascending=False).reset_index(drop=True)


def get_announcements(start: date, end: date, symbols: list[str] | None = None,
                      client: http.Client | None = None) -> pd.DataFrame:
    """One row per seq_id. symbols=None -> whole market, one request per day (cached per day)."""
    c = client or http.client()
    fmt = "%d-%m-%Y"
    frames = []
    if symbols:
        for sym in symbols:
            r = c.get(API, {"index": "equities", "symbol": sym, "from_date": start.strftime(fmt),
                            "to_date": end.strftime(fmt)}, site="nse", policy=http.window_policy(end, c))
            frames.append(parse_announcements(r.raise_for_status().content))
    else:
        d = start
        while d <= end:
            r = c.get(API, {"index": "equities", "from_date": d.strftime(fmt), "to_date": d.strftime(fmt)},
                      site="nse", policy=http.window_policy(d, c))
            frames.append(parse_announcements(r.raise_for_status().content))
            d += timedelta(days=1)
    return combine(frames)
