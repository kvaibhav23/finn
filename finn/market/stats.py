"""Key numbers for a company page: price figures from the bhavcopy, results figures from XBRL.

Every value carries how it was made (formula) and where it came from (XBRL URL or NSE file). A value
that cannot be computed from filed data is None, with a reason; nothing is estimated.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd

from finn.data.corporate_actions import adjust_per_share, factor_after
from finn.ledger.periods import fy_label

CR = 1e7   # XBRL values are in rupees; the site shows ₹ crore


def _f(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _ago(rows: list[dict], key: str, end: date, days: int) -> dict | None:
    """The last row on or before end - days (prices) or None if history is shorter."""
    cut = end - timedelta(days=days)
    past = [r for r in rows if r[key] <= cut]
    return past[-1] if past else None


def price_stats(rows: list[dict], nifty: list[dict]) -> dict | None:
    if not rows:
        return None
    last, end = rows[-1], rows[-1]["date"]
    prev = rows[-2] if len(rows) > 1 else None
    year = [r for r in rows if r["date"] > end - timedelta(days=365)]
    a, n_last = _ago(rows, "date", end, 365), (nifty[-1] if nifty else None)
    n_ago = _ago(nifty, "date", end, 365) if nifty else None
    deliv = [r["deliv_pct"] for r in rows if r.get("deliv_pct") is not None]
    hi, lo = max(r["high"] for r in year), min(r["low"] for r in year)
    return {
        "as_of": end.isoformat(), "close": last["close"],
        "change": last["close"] - prev["close"] if prev else None,
        "change_pct": (last["close"] / prev["close"] - 1) * 100 if prev and prev["close"] else None,
        "high_52w": hi, "low_52w": lo,
        "range_position": (last["close"] - lo) / (hi - lo) if hi > lo else None,
        "return_1y": (last["close"] / a["close"] - 1) * 100 if a and a["close"] else None,
        "nifty_return_1y": (n_last["close"] / n_ago["close"] - 1) * 100
        if n_last and n_ago and n_last["date"] == end else None,
        "delivery_20d": sum(deliv[-20:]) / len(deliv[-20:]) if len(deliv) >= 20 else None,
        "delivery_avg": sum(deliv) / len(deliv) if len(deliv) >= 40 else None,
        "delivery_sessions": len(deliv),
    }


def _consecutive(qes: list[date]) -> bool:
    p = [pd.Period(q, freq="Q") for q in qes]
    return all((b - a).n == 1 for a, b in zip(p, p[1:]))


def results_stats(fin: pd.DataFrame, actions: pd.DataFrame | None, close: float | None) -> dict | None:
    """From quarterly XBRL rows (oldest first). Uses one basis throughout: the latest quarter's."""
    if fin is None or fin.empty:
        return None
    basis = fin["basis"].iloc[-1]
    df = fin[fin["basis"] == basis].sort_values("qe").reset_index(drop=True)
    acts = actions if actions is not None else pd.DataFrame(columns=["factor", "ex_date", "subject"])
    df = adjust_per_share(df, acts) if "board_meeting" in df else df
    bank = df["taxonomy"].iloc[-1] == "banking"
    lender = df["taxonomy"].iloc[-1] in ("banking", "nbfc")
    top = "total_income" if bank else "revenue"
    latest = df.iloc[-1]
    out = {"basis": basis, "bank": bool(bank), "latest_quarter": fy_label(latest["qe"]),
           "latest_qe": latest["qe"].isoformat(), "xbrl_url": latest.get("xbrl_url"), "top_line": top}

    last4 = df.tail(4)
    full_year = len(last4) == 4 and _consecutive(list(last4["qe"]))
    s = lambda col: _f(last4[col].sum(min_count=4)) if full_year else None
    ttm_top, ttm_pat = s(top), s("pat")
    out["ttm_revenue_cr"] = ttm_top / CR if ttm_top is not None else None
    out["ttm_pat_cr"] = ttm_pat / CR if ttm_pat is not None else None
    out["ttm_margin_pct"] = ttm_pat / ttm_top * 100 if ttm_top and ttm_pat is not None else None

    eps_col = "eps_diluted_adj" if "eps_diluted_adj" in df else "eps_diluted"
    ttm_eps = s(eps_col)
    out["ttm_eps"] = ttm_eps
    if close is None or ttm_eps is None:
        out["pe"], out["pe_note"] = None, "not enough filed quarters"
    elif ttm_eps <= 0:
        out["pe"], out["pe_note"] = None, "loss-making over the last four quarters"
    else:
        out["pe"], out["pe_note"] = close / ttm_eps, None

    # Shares from the latest quarter that tagged them properly (a misfiled face value leaves a quarter blank).
    with_shares = df[df["shares_outstanding"].map(_f).notna()]
    src = with_shares.iloc[-1] if len(with_shares) else latest
    shares = _f(src.get("shares_outstanding"))
    if shares is not None and close is not None:
        pub = src.get("board_meeting")
        f = factor_after(acts, date.fromisoformat(str(pub)[:10]))[0] if pub and not acts.empty else 1.0
        out["market_cap_cr"] = shares * f * close / CR
    else:
        out["market_cap_cr"] = None

    prior = df[df["qe"] == (pd.Period(latest["qe"], freq="Q") - 4).end_time.date()]
    yoy = lambda col: (_f(latest[col]) / _f(prior[col].iloc[0]) - 1) * 100 \
        if len(prior) and _f(latest[col]) is not None and _f(prior[col].iloc[0]) else None
    out["revenue_yoy_pct"], out["pat_yoy_pct"] = yoy(top), yoy("pat")
    out["net_npa_pct"] = _f(latest.get("net_npa_pct")) if bank else None
    cr = lambda r, col: _f(r.get(col)) / CR if _f(r.get(col)) is not None else None
    # Revenue, EBITDA, PBT and PAT for the results card (vs the quarter before and a year before). EBITDA is
    # derived (pbt + finance costs + depreciation - other income) and is None for banks, with the reason.
    out["ebitda_note"] = ("EBITDA is not meaningful for banks" if bank else
                          "EBITDA is not meaningful for lenders" if lender else None)
    out["quarters"] = [{"quarter": fy_label(r["qe"]), "qe": r["qe"].isoformat(),
                        "revenue_cr": cr(r, top), "ebitda_cr": None if lender else cr(r, "ebitda"),
                        "pbt_cr": cr(r, "pbt"), "pat_cr": cr(r, "pat"),
                        "approved": str(r["board_meeting"])[:10] if r.get("board_meeting") else None,
                        "xbrl_url": r.get("xbrl_url")} for _, r in df.tail(9).iterrows()]
    return out


def _change(now: float | None, then: float | None) -> float | None:
    """Percent change; None when either is missing or the base was zero or a loss (a % on a loss misleads)."""
    return (now / then - 1) * 100 if now is not None and then is not None and then > 0 else None


def results_card(results: dict | None, qe: str | None = None) -> dict | None:
    """Revenue, EBITDA, PBT and PAT for one quarter (default: the latest), against the quarter before and the
    same quarter a year earlier. Only exact quarters count: a gap in the filings gives None, never a guess."""
    qs = (results or {}).get("quarters") or []
    by_qe = {q["qe"]: q for q in qs}
    cur = by_qe.get(qe) if qe else (qs[-1] if qs else None)
    if not cur:
        return None
    p = pd.Period(cur["qe"], freq="Q")
    prev, year = by_qe.get(str((p - 1).end_time.date())), by_qe.get(str((p - 4).end_time.date()))
    top = results.get("top_line", "revenue")
    rows = []
    for key, col in ((top, "revenue_cr"), ("ebitda", "ebitda_cr"), ("pbt", "pbt_cr"), ("pat", "pat_cr")):
        now = cur.get(col)
        row = {"key": key, "now": now,
               "qoq": _change(now, (prev or {}).get(col)), "yoy": _change(now, (year or {}).get(col))}
        if key == "ebitda" and results.get("ebitda_note"):
            row["note"] = results["ebitda_note"]
        rows.append(row)
    return {"quarter": cur["quarter"], "qe": cur["qe"], "approved": cur.get("approved"),
            "basis": results.get("basis"), "xbrl_url": cur.get("xbrl_url"),
            "prev_quarter": prev["quarter"] if prev else None, "year_quarter": year["quarter"] if year else None,
            "rows": rows}


def card_for_filing(results: dict | None, filed: str | None, days: int = 3) -> dict | None:
    """The card for the quarter whose results the board approved within `days` of this filing, if NSE's XBRL
    for it is in; otherwise None and the digest links the PDF."""
    if not filed:
        return None
    day = date.fromisoformat(filed[:10])
    for q in reversed((results or {}).get("quarters") or []):
        if q.get("approved") and abs((date.fromisoformat(q["approved"]) - day).days) <= days:
            return results_card(results, q["qe"])
    return None
