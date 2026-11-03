"""Signals for a company page, each a set of facts with a fixed state word; no score and no buy/sell view.

States are chosen by thresholds here; the website turns facts + state into a sentence in the reader's
language (web/lib/sentences.ts), so every language says the same thing with the same numbers.
"""
from __future__ import annotations

MIN_CHECKED = 3        # fewer decided promises than this is too few to describe a track record
NEAR = 0.15            # within 15% of the 52-week range from either end counts as "near"
DELIVERY_GAP = 5.0     # percentage points between recent and usual delivery to call it different


def track_record(counts: dict | None) -> dict:
    if not counts:
        return {"key": "track", "state": "none", "facts": {}}
    kept, missed, dropped = counts.get("Kept", 0), counts.get("Missed", 0), counts.get("Dropped", 0)
    decided = kept + missed
    return {"key": "track", "state": "enough" if decided >= MIN_CHECKED else "few",
            "facts": {"kept": kept, "missed": missed, "decided": decided, "dropped": dropped}}


def price_trend(p: dict | None) -> dict | None:
    if not p or p.get("return_1y") is None:
        return None
    pos = p.get("range_position")
    where = None if pos is None else "low" if pos <= NEAR else "high" if pos >= 1 - NEAR else "middle"
    return {"key": "price", "state": where or "unknown",
            "facts": {"return_1y": p["return_1y"], "nifty_return_1y": p.get("nifty_return_1y"),
                      "close": p["close"], "low_52w": p["low_52w"], "high_52w": p["high_52w"]}}


def delivery(p: dict | None) -> dict | None:
    if not p or p.get("delivery_20d") is None or p.get("delivery_avg") is None:
        return None
    recent, usual = p["delivery_20d"], p["delivery_avg"]
    gap = recent - usual
    state = "higher" if gap >= DELIVERY_GAP else "lower" if gap <= -DELIVERY_GAP else "usual"
    return {"key": "delivery", "state": state,
            "facts": {"recent": recent, "usual": usual, "months": round(p["delivery_sessions"] / 21)}}


def filings_flag(filings: list[dict], days: int) -> dict:
    flagged = [f for f in filings if f["worth_a_look"]]
    return {"key": "filings", "state": "flagged" if flagged else "clear",
            "facts": {"count": len(flagged), "days": days, "tags": list(dict.fromkeys(f["tag"] for f in flagged))},
            "items": [{"date": f["date"], "tag": f["tag"], "pdf_url": f["pdf_url"]} for f in flagged[:5]]}


def move_signal(move: dict | None) -> dict | None:
    if not move:
        return None
    return {"key": "move", "state": "down" if move["change_pct"] < 0 else "up",
            "facts": {k: v for k, v in move.items() if k != "filings"}, "items": move["filings"]}


def signals(price: dict | None, counts: dict | None, filings: list[dict] | None, days: int,
            move: dict | None = None) -> list[dict]:
    out = [move_signal(move), track_record(counts), price_trend(price), delivery(price)]
    if filings is not None:
        out.append(filings_flag(filings, days))
    return [s for s in out if s]
