"""Stage 3: thread the same promise across calls -> Reaffirmed / Revised (old -> new) / Dropped.

Numeric metrics are linked by code (same metric, basis and horizon end). Milestone / direction /
other promises are linked by the model, which may only return an id from the list it was given.
Dropped is decided by code, and only after every later call's management sentences were searched.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel

from finn import llm

CODE_LINKED = ("revenue_growth", "ebitda_margin", "pbdit_margin", "pat", "volume_growth", "capex",
               "order_book", "debt")
METRIC_WORDS = {
    "revenue_growth": r"revenue|top[- ]?line|sales|growth",
    "ebitda_margin": r"EBITDA|margin",
    "pbdit_margin": r"PBDIT|EBITDA|margin",
    "pat": r"\bPAT\b|profit|bottom[- ]?line",
    "volume_growth": r"volume",
    "capex": r"capex|capital expenditure|invest",
    "order_book": r"order ?book|orders",
    "debt": r"debt|borrowing|leverage",
}
STOP = {"with", "from", "that", "this", "will", "into", "over", "their", "have", "growth", "business"}


class Link(BaseModel):
    new_id: str
    match_id: str


class Links(BaseModel):
    links: list[Link]


LINK_PROMPT = """Earlier promises made by {symbol} management are listed under EARLIER, new ones from a later
call under NEW. For each NEW promise, return match_id = the id of the EARLIER promise that is the same
commitment (same subject; the target or deadline may have changed), or "" if none is the same.
Only use ids from EARLIER.

EARLIER:
{earlier}

NEW:
{new}
"""


def _key(c: dict) -> tuple:
    h = c.get("horizon") or {}
    return c["metric"], c["basis"], h.get("end")


def _target_sig(c: dict) -> tuple:
    t, h = c["target"], c.get("horizon") or {}
    return t["kind"], t["low"], t["high"], t["comparator"], h.get("end")


def _version(c: dict, status: str) -> dict:
    return {k: c.get(k) for k in ("id", "quarter", "quarter_end", "page", "speaker", "quote", "target",
                                  "horizon", "conditional", "basis", "subject")} | {"status": status}


def _append(th: dict, c: dict) -> None:
    prev = th["versions"][-1]
    if _target_sig(c) == _target_sig(prev):
        th["versions"].append(_version(c, "Reaffirmed"))
    else:
        th["versions"].append(_version(c, "Revised") | {"revised_from": {"target": prev["target"],
                                                                          "horizon": prev["horizon"]}})


def thread(classified_by_call: list[list[dict]], symbol: str, model: str | None = None) -> list[dict]:
    """classified_by_call: per call (oldest first), the commitments that passed the guards."""
    threads: list[dict] = []
    for k, rows in enumerate(classified_by_call):
        llm_new = []
        for c in rows:
            if c["metric"] in CODE_LINKED:
                same = [t for t in threads if t["key"] == _key(c)]
                if same and same[-1]["versions"][-1]["quarter"] == c["quarter"]:   # repeated within one call
                    same[-1]["versions"][-1].setdefault("also_said", []).append(c["id"])
                    continue
                if same:
                    _append(same[-1], c)
                    continue
                threads.append({"id": c["id"], "metric": c["metric"], "key": _key(c), "versions": [_version(c, "New")]})
            else:
                llm_new.append(c)
        earlier = [t for t in threads if t["metric"] not in CODE_LINKED and t["versions"][-1]["quarter_end"] < rows[0]["quarter_end"]] if rows else []
        matches = {}
        if llm_new and earlier:
            fmt = lambda t: {"id": t["id"], "metric": t["metric"], "subject": t["versions"][-1]["subject"],
                             "quote": t["versions"][-1]["quote"]}
            prompt = LINK_PROMPT.format(symbol=symbol, earlier=json.dumps([fmt(t) for t in earlier], ensure_ascii=False),
                                        new=json.dumps([{"id": c["id"], "metric": c["metric"], "subject": c["subject"],
                                                         "quote": c["quote"]} for c in llm_new], ensure_ascii=False))
            ids = {t["id"] for t in earlier}
            matches = {l.new_id: l.match_id for l in llm.call("thread", prompt, Links, symbol=symbol, model=model).links
                       if l.match_id in ids}   # an id the model invented is ignored
        for c in llm_new:
            target = next((t for t in earlier if t["id"] == matches.get(c["id"])), None)
            if target:
                _append(target, c)
            else:
                threads.append({"id": c["id"], "metric": c["metric"], "key": _key(c), "versions": [_version(c, "New")]})
    return threads


def mention_pattern(th: dict) -> re.Pattern:
    """What counts as 'still talked about' in a later call: the metric's words, or the subject's."""
    if th["metric"] in METRIC_WORDS:
        return re.compile(METRIC_WORDS[th["metric"]], re.I)
    words = [w for w in re.findall(r"[A-Za-z]{4,}", th["versions"][-1].get("subject") or "") if w.lower() not in STOP]
    return re.compile("|".join(rf"\b{re.escape(w)}" for w in words) or r"(?!x)x", re.I)


def mark_dropped(threads: list[dict], calls: list[dict], xbrl_resolvable) -> None:
    """Dropped = not resolvable from XBRL, at least one later call processed, and no later call's
    management sentences mention the metric/subject. Records the quarters searched either way."""
    for th in threads:
        last_q = th["versions"][-1]["quarter_end"]
        later = [c for c in calls if c["quarter_end"] > last_q]
        th["searched_later"] = [c["quarter"] for c in later]
        pat = mention_pattern(th)
        th["mentioned_later"] = [c["quarter"] for c in later if any(pat.search(s["sentence"]) for s in c["sentences"])]
        th["dropped"] = bool(later) and not th["mentioned_later"] and not xbrl_resolvable(th)
