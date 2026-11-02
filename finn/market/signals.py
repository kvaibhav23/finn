"""Four signals for a company page, each a fact with its source; no score and no buy/sell view.

Words are chosen by fixed thresholds in code. Every number in a sentence comes from the inputs.
"""
from __future__ import annotations

MIN_CHECKED = 3        # fewer decided promises than this is too few to describe a track record
NEAR = 0.15            # within 15% of the 52-week range from either end counts as "near"
DELIVERY_GAP = 5.0     # percentage points between recent and usual delivery to call it different


def _pct(v: float, signed: bool = True) -> str:
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"


def track_record(counts: dict | None) -> dict:
    s = {"key": "track", "label": "Track record", "source": "promises"}
    if not counts:
        return s | {"text": "FINN hasn't checked this company's promises yet.", "detail": None}
    kept, missed, dropped = counts.get("Kept", 0), counts.get("Missed", 0), counts.get("Dropped", 0)
    decided = kept + missed
    if decided < MIN_CHECKED:
        text = (f"Only {decided} promise{'s' if decided != 1 else ''} can be checked against results so far, "
                "too few to judge.")
    else:
        text = f"Kept {kept} of the {decided} promises whose results are in."
    detail = f"{dropped} more {'was' if dropped == 1 else 'were'} never mentioned again." if dropped else None
    return s | {"text": text, "detail": detail}


def price_trend(p: dict | None) -> dict | None:
    if not p or p.get("return_1y") is None:
        return None
    r, n = p["return_1y"], p.get("nifty_return_1y")
    text = f"{'Up' if r >= 0 else 'Down'} {abs(r):.1f}% in a year"
    text += f"; the Nifty 50 {'rose' if n >= 0 else 'fell'} {abs(n):.1f}% over the same days." if n is not None else "."
    pos = p.get("range_position")
    if pos is None:
        where = None
    elif pos <= NEAR:
        where = "near its 52-week low"
    elif pos >= 1 - NEAR:
        where = "near its 52-week high"
    else:
        where = "between its 52-week low and high"
    detail = (f"Closed at ₹{p['close']:,.2f}, {where} (₹{p['low_52w']:,.2f} to ₹{p['high_52w']:,.2f})."
              if where else None)
    return {"key": "price", "label": "Price trend", "text": text, "detail": detail, "source": "prices"}


def delivery(p: dict | None) -> dict | None:
    if not p or p.get("delivery_20d") is None or p.get("delivery_avg") is None:
        return None
    recent, usual = p["delivery_20d"], p["delivery_avg"]
    gap = recent - usual
    if gap >= DELIVERY_GAP:
        meaning = "Higher than usual: more buyers kept the shares instead of selling them the same day."
    elif gap <= -DELIVERY_GAP:
        meaning = "Lower than usual: more of the trading was bought and sold within the day."
    else:
        meaning = "About usual for this stock."
    months = round(p["delivery_sessions"] / 21)
    return {"key": "delivery", "label": "Delivery",
            "text": f"{recent:.0f}% of shares traded in the last 20 sessions were delivered, against "
                    f"{usual:.0f}% over the last {months} months.",
            "detail": meaning, "source": "prices"}


def filings_flag(filings: list[dict], days: int) -> dict:
    flagged = [f for f in filings if f["worth_a_look"]]
    if not flagged:
        text = (f"No resignations, auditor changes, pledges, credit ratings or regulatory orders filed "
                f"in the last {days} days.")
    else:
        kinds = ", ".join(dict.fromkeys(f["tag"].lower() for f in flagged))
        text = f"{len(flagged)} filing{'s' if len(flagged) != 1 else ''} worth a look in the last {days} days: {kinds}."
    return {"key": "filings", "label": "Filings", "text": text, "detail": None, "source": "filings",
            "items": [{"date": f["date"], "tag": f["tag"], "pdf_url": f["pdf_url"]} for f in flagged[:5]]}


def signals(price: dict | None, counts: dict | None, filings: list[dict] | None, days: int) -> list[dict]:
    out = [track_record(counts), price_trend(price), delivery(price)]
    if filings is not None:
        out.append(filings_flag(filings, days))
    return [s for s in out if s]
