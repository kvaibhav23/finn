"""NSE corporate actions (bonus, split, dividend ...) and per-share adjustment (trap 3).

A 1:1 bonus doubles the share count, so EPS published before it must be divided by 2 to
compare with EPS published after it (HDFCBANK: 23.11 in Dec-24 vs ~13 after the Aug-2025 bonus).

Adjustment keys on the date the numbers were *published* (board meeting), not the quarter-end:
under Ind AS 33, results approved after a bonus already present restated EPS, so keying on
quarter-end would double-adjust the quarter in which the bonus happened.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime

import pandas as pd

from . import http

API = "https://www.nseindia.com/api/corporates-corporateActions"
COLUMNS = ["symbol", "subject", "type", "ex_date", "record_date", "factor", "ratio"]


def classify(subject: str) -> tuple[str, float, str | None]:
    """-> (type, share-count factor, ratio text). factor=1.0 when the share count is unchanged."""
    s = " ".join(subject.split())
    if m := re.search(r"bonus\s*(\d+)\s*:\s*(\d+)", s, re.I):
        a, b = int(m.group(1)), int(m.group(2))
        return "bonus", (a + b) / b, f"{a}:{b}"
    if m := re.search(r"(split|sub-?division).*?from\s*rs\.?\s*([\d.]+).*?to\s*rs\.?\s*([\d.]+)", s, re.I):
        old, new = float(m.group(2)), float(m.group(3))
        return "split", old / new, f"FV {old:g} -> {new:g}"
    if m := re.search(r"consolidation.*?from\s*rs\.?\s*([\d.]+).*?to\s*rs\.?\s*([\d.]+)", s, re.I):
        old, new = float(m.group(1)), float(m.group(2))
        return "consolidation", old / new, f"FV {old:g} -> {new:g}"
    if re.search(r"rights", s, re.I):
        return "rights", 1.0, None   # rights issues are paid for; not a pure share-count change
    if re.search(r"dividend", s, re.I):
        return "dividend", 1.0, None
    return "other", 1.0, None


def _date(s) -> date | None:
    try:
        return datetime.strptime(str(s).strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


def parse_corporate_actions(content: bytes | list) -> pd.DataFrame:
    rows = json.loads(content) if isinstance(content, (bytes, str)) else content
    out = []
    for r in rows:
        subject = " ".join((r.get("subject") or "").split())
        kind, factor, ratio = classify(subject)
        out.append({"symbol": r.get("symbol"), "subject": subject, "type": kind,
                    "ex_date": _date(r.get("exDate")), "record_date": _date(r.get("recDate")),
                    "factor": factor, "ratio": ratio})
    df = pd.DataFrame(out, columns=COLUMNS)
    return df.sort_values("ex_date", ascending=False, na_position="last").reset_index(drop=True)


def get_corporate_actions(symbol: str, client: http.Client | None = None) -> pd.DataFrame:
    c = client or http.client()
    r = c.get(API, {"index": "equities", "symbol": symbol}, site="nse", policy="daily").raise_for_status()
    return parse_corporate_actions(r.content)


def _as_date(v) -> date | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, str):
        return date.fromisoformat(v[:10])
    if isinstance(v, datetime) or hasattr(v, "to_pydatetime"):
        return v.date()
    return v


def factor_after(actions: pd.DataFrame, published: date) -> tuple[float, list[str]]:
    """Cumulative share-count factor of actions with ex-date after `published`, and their subjects."""
    later = actions[(actions["factor"] != 1.0) & actions["ex_date"].notna() & (actions["ex_date"] > published)]
    return float(later["factor"].prod()) if len(later) else 1.0, list(later["subject"])


def adjust_per_share(df: pd.DataFrame, actions: pd.DataFrame,
                     cols: tuple[str, ...] = ("eps_basic", "eps_diluted"),
                     published_col: str = "board_meeting") -> pd.DataFrame:
    """Express per-share values in today's share terms. Adds `<col>_adj` + `adj_factor` columns
    and a receipt per adjusted column; original values stay untouched."""
    df = df.copy()
    df["receipts"] = [dict(r) for r in df["receipts"]] if "receipts" in df else [{} for _ in range(len(df))]
    factors = []
    for i, r in df.iterrows():
        pub = _as_date(r.get(published_col))
        f, why = factor_after(actions, pub) if pub else (math.nan, [])
        factors.append(f)
        for col in cols:
            if col in df:
                df.at[i, "receipts"][f"{col}_adj"] = {"derived": True, "formula": f"{col} / adj_factor",
                                                      "adj_factor": f, "actions": why,
                                                      "published": pub.isoformat() if pub else None}
    df["adj_factor"] = factors
    for col in cols:
        if col in df:
            df[f"{col}_adj"] = df[col] / df["adj_factor"]
    return df
