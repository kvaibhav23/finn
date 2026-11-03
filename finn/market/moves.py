"""Unusual one-day moves, for a stock and for the market. Facts only: how big, compared with what is
normal for this stock, on how much volume, and which filings came out that day. FINN never says why
a price moved; the filings are listed so a reader can judge.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from statistics import median

BIG_PCT = 5.0          # a 5% day is big for any stock
TIMES = 3.0            # ... or three times this stock's typical daily move,
MIN_PCT = 2.0          # ... as long as it is at least 2%
VOLUME_WINDOW = 50     # sessions in the "usual volume" average
MARKET_PCT = 2.0       # Nifty 50 moves of 2% or more get a line on the home page


def _returns(rows: list[dict]) -> list[tuple[date, float]]:
    return [(b["date"], (b["close"] / a["close"] - 1) * 100) for a, b in zip(rows, rows[1:]) if a["close"]]


def big_move(rows: list[dict], filings: list[dict] | None = None, nifty: list[dict] | None = None) -> dict | None:
    """The last session's move if it was unusual, else None."""
    rets = _returns(rows)
    if len(rets) < 20:
        return None
    day, pct = rets[-1]
    past = [abs(r) for _, r in rets[:-1][-250:]]
    typical = median(past)
    if not (abs(pct) >= BIG_PCT or (abs(pct) >= MIN_PCT and typical and abs(pct) >= TIMES * typical)):
        return None
    vols = [r["volume"] for r in rows[:-1][-VOLUME_WINDOW:] if r["volume"]]
    year = [r for d, r in rets[:-1] if d > day - timedelta(days=365)]
    same_way = [abs(r) for r in year if (r < 0) == (pct < 0)]
    prev_day = rows[-2]["date"]
    n = {x["date"]: x["close"] for x in nifty or []}
    nifty_pct = (n[day] / n[prev_day] - 1) * 100 if day in n and prev_day in n and n[prev_day] else None
    # filings since the previous close: they could be what the market reacted to
    that_day = [f for f in filings or [] if f.get("date") and prev_day.isoformat() <= f["date"] <= day.isoformat()]
    return {"date": day.isoformat(), "change_pct": pct, "typical_pct": typical,
            "times": abs(pct) / typical if typical else None,
            "volume_x": rows[-1]["volume"] / (sum(vols) / len(vols)) if vols else None,
            "biggest_in_year": bool(same_way) and abs(pct) > max(same_way),
            "nifty_change_pct": nifty_pct,
            "filings": [{"date": f["date"], "tag": f["tag"], "pdf_url": f["pdf_url"]} for f in that_day[:5]]}


def market_day(nifty: list[dict]) -> dict | None:
    """The Nifty 50's last session, flagged when the move is big enough for the home page."""
    if len(nifty) < 2:
        return None
    a, b = nifty[-2], nifty[-1]
    pct = (b["close"] / a["close"] - 1) * 100
    return {"date": b["date"].isoformat(), "close": b["close"], "change_pct": pct, "big": abs(pct) >= MARKET_PCT}


def event_id(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def events(symbol: str, now: dict, before: dict | None) -> list[dict]:
    """What changed since the last run, for alerts: a new big move, new filings worth a look or new results,
    and a rerun of the promise ledger. The first run for a company sends nothing (nothing to compare)."""
    if not before:
        return []
    out = []
    move, old_move = now.get("move"), before.get("move")
    if move and (not old_move or old_move["date"] != move["date"]):
        out.append({"id": event_id(symbol, "move", move["date"]), "symbol": symbol, "kind": "move",
                    "date": move["date"], "facts": {k: move[k] for k in ("change_pct", "times", "biggest_in_year")}})
    seen = {f["pdf_url"] for f in before.get("filings") or []}
    for f in now.get("filings") or []:
        if f["pdf_url"] in seen or not (f["worth_a_look"] or f["tag"] == "Results"):
            continue
        out.append({"id": event_id(symbol, "filing", f["pdf_url"]), "symbol": symbol,
                    "kind": "results" if f["tag"] == "Results" else "flag", "date": f["date"],
                    "facts": {"tag": f["tag"], "pdf_url": f["pdf_url"]}})
    led, old_led = now.get("ledger_generated_at"), before.get("ledger_generated_at")
    if led and old_led and led != old_led:
        out.append({"id": event_id(symbol, "ledger", led), "symbol": symbol, "kind": "ledger", "date": led[:10],
                    "facts": now.get("ledger_counts") or {}})
    return out
