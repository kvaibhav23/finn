"""Stage 5: verdicts by code rules; the model only writes a one-line explanation.

Kept / Missed  : the period has ended and an actual exists (beating a band on a higher-is-better
                 metric counts as Kept, noted "above range").
On track       : not due; the interim (year-to-date) actual already meets the target.
Revised        : not due; the latest call changed the target or deadline.
Pending        : not due, or no deadline, with no interim evidence (or interim off target).
Dropped        : see thread.mark_dropped.
Unverifiable   : due, but no XBRL series and no management figure.
An explanation that contains any number not present in the facts is replaced by a template.
"""
from __future__ import annotations

import json
from datetime import date

from pydantic import BaseModel

from finn import llm

from .classify import numbers
from .thread import effective

HIGHER_BETTER = {"revenue_growth", "ebitda_margin", "pbdit_margin", "pat", "volume_growth", "order_book"}
ABOUT_PP, ABOUT_REL = 1.0, 0.10


def meets(target: dict, actual: float, metric: str) -> tuple[bool | None, str]:
    """(met?, note). None when the target cannot be compared numerically."""
    lo, hi, cmp_, unit = target.get("low"), target.get("high"), target["comparator"], target["unit"]
    if target["kind"] == "range" and lo is not None and hi is not None:
        if lo <= actual <= hi:
            return True, "within range"
        if actual > hi:
            return (True, "above range") if metric in HIGHER_BETTER else (False, "above range")
        return False, "below range"
    if target["kind"] == "value":
        v = lo if lo is not None else hi
        if v is None:
            return None, "no target value"
        if cmp_ == "at_least":
            return actual >= v, "at least"
        if cmp_ == "at_most":
            return actual <= v, "at most"
        tol = ABOUT_PP if unit == "pct" else abs(v) * ABOUT_REL
        if abs(actual - v) <= tol:
            return True, "about (within tolerance)"
        if actual > v and metric in HIGHER_BETTER:
            return True, "above target"
        return False, "outside tolerance"
    if target["kind"] == "direction" and cmp_ in ("up", "down"):
        return (actual > 0) == (cmp_ == "up"), f"direction {cmp_}"
    return None, "target not numerically comparable"


def decide(th: dict, res: dict, as_of: date | None) -> tuple[str, str]:
    """(verdict, rule) from the thread, its resolution and the latest reported quarter."""
    v = effective(th)
    h = v["horizon"]
    revised = any(x["status"] == "Revised" for x in th["versions"])
    if th.get("dropped"):
        return "Dropped", f"not mentioned in later calls ({', '.join(th['searched_later'])})"
    final = res.get("final")
    if final is not None:
        if final == "event_done":
            return "Kept", "management later reported it done"
        if final == "event_delayed":
            return "Missed", "management later reported it delayed / not done"
        ok, why = meets(v["target"], final, th["metric"])
        if ok is None:
            return "Unverifiable", why
        return ("Kept" if ok else "Missed"), why + (" (against the revised target)" if revised else "")
    due = h is not None and as_of is not None and h["end"] <= as_of
    if not due:
        interim = res.get("interim")
        interim_ok = meets(v["target"], interim, th["metric"])[0] if isinstance(interim, float) else None
        if interim_ok:
            return "On track", "interim actual meets the target"
        if revised:
            return "Revised", "target or deadline changed in a later call"
        return "Pending", "no deadline stated" if h is None else (
            "interim actual off target" if interim_ok is False else "not due yet")
    return "Unverifiable", res.get("note") or "no actual found"


class Line(BaseModel):
    id: str
    line: str


class Lines(BaseModel):
    lines: list[Line]


EXPLAIN_PROMPT = """Write ONE short plain-English line (max 25 words) per item explaining why the promise got its
verdict. Use only the facts given; do not add numbers that are not in the facts; do not change the verdict.

{items}
"""


def template(f: dict) -> str:
    actual = f"actual {f['actual']} ({f['source']})" if f.get("actual") is not None else f"no actual ({f['source']})"
    return f"{f['verdict']}: target {f['target']} by {f['due']}; {actual}; rule: {f['rule']}."


def explain(facts: list[dict], symbol: str, model: str | None = None) -> dict[str, str]:
    """facts: [{id, promise, target, due, actual, source, verdict, rule}] -> id -> line."""
    if not facts:
        return {}
    got = {l.id: l.line for l in llm.call("explain", EXPLAIN_PROMPT.format(items=json.dumps(facts, ensure_ascii=False,
                                                                                          default=str)),
                                          Lines, symbol=symbol, model=model).lines}
    out = {}
    for f in facts:
        line = got.get(f["id"], "")
        allowed = set(numbers(json.dumps(f, default=str)))
        out[f["id"]] = line if line and set(numbers(line)) <= allowed else template(f)
    return out
