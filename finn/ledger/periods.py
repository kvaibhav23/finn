"""Indian fiscal-year arithmetic. FY27 = Apr-2026..Mar-2027; Q1 ends 30-Jun, Q4 ends 31-Mar.

Horizon tokens come from the classifier; turning them into dates is done here, by code,
relative to the call. A results call for quarter Q is held during Q+1, so "current quarter"
is Q+1 and "next quarter" Q+2.
"""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

Q_END = {1: (6, 30), 2: (9, 30), 3: (12, 31), 4: (3, 31)}


def fy_of(qe: date) -> int:
    return qe.year + (qe.month > 3)


def quarter_no(qe: date) -> int:
    return {6: 1, 9: 2, 12: 3, 3: 4}[qe.month]


def fy_label(qe: date) -> str:
    """2026-03-31 -> Q4FY26, 2026-06-30 -> Q1FY27."""
    return f"Q{quarter_no(qe)}FY{fy_of(qe) % 100:02d}"


def quarter_end(fy: int, q: int) -> date:
    m, d = Q_END[q]
    return date(fy if q == 4 else fy - 1, m, d)


def shift(qe: date, n: int) -> date:
    return (pd.Period(qe, freq="Q") + n).end_time.date()


def _fy(two_or_four: str) -> int:
    y = int(two_or_four)
    return y if y > 1000 else 2000 + y


def resolve_horizon(token: str | None, call_qe: date) -> dict | None:
    """-> {"end": date, "quarters": [quarter-ends in the period], "assumed": bool, "token": token}
    or None when the horizon is open-ended ("medium_term") or unreadable."""
    t = (token or "none").strip().replace(" ", "").upper()
    run = shift(call_qe, 1)                    # the quarter in which the call is held
    if m := re.fullmatch(r"Q([1-4])FY(\d{2}|\d{4})", t):
        q = quarter_end(_fy(m[2]), int(m[1]))
        return {"end": q, "quarters": [q], "assumed": False, "token": token}
    if m := re.fullmatch(r"H([12])FY(\d{2}|\d{4})", t):
        fy, h = _fy(m[2]), int(m[1])
        qs = [quarter_end(fy, q) for q in ((1, 2) if h == 1 else (3, 4))]
        return {"end": qs[-1], "quarters": qs, "assumed": False, "token": token}
    if m := re.fullmatch(r"FY(\d{2}|\d{4})", t):
        fy = _fy(m[1])
        return {"end": quarter_end(fy, 4), "quarters": [quarter_end(fy, q) for q in (1, 2, 3, 4)],
                "assumed": False, "token": token}
    rel = {"CURRENT_QUARTER": 1, "THIS_QUARTER": 1, "NEXT_QUARTER": 2}
    if t in rel:
        q = shift(call_qe, rel[t])
        return {"end": q, "quarters": [q], "assumed": False, "token": token}
    if t in ("CURRENT_YEAR", "THIS_YEAR", "NEXT_YEAR", "NONE"):
        fy = fy_of(run) + (t == "NEXT_YEAR")
        return {"end": quarter_end(fy, 4), "quarters": [quarter_end(fy, q) for q in (1, 2, 3, 4)],
                "assumed": t == "NONE", "token": token}
    return None
