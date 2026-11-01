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


def code_linked(c: dict) -> bool:
    """Company-wide numeric metrics are linked by code; segment-level ones need the subject (model)."""
    return c["metric"] in CODE_LINKED and c.get("scope", "company") == "company"


def _key(c: dict) -> tuple:
    h = c.get("horizon") or {}
    return c["metric"], h.get("end"), c["target"]["unit"] if has_target(c) else None


def _basis_ok(th: dict, c: dict) -> bool:
    """"unspecified" links with either basis; standalone never links with consolidated."""
    b = {v["basis"] for v in th["versions"]} - {"unspecified"}
    return c["basis"] == "unspecified" or not b or c["basis"] in b


def has_target(v: dict) -> bool:
    return bool(v.get("target")) and v["target"]["kind"] != "none"


def effective(th: dict) -> dict:
    """The latest version that states a target ("we'll maintain our guidance" restates no number)."""
    return next((v for v in reversed(th["versions"]) if has_target(v)), th["versions"][-1])


def _target_sig(v: dict) -> tuple:
    t, h = v["target"], v.get("horizon") or {}
    return t["kind"], t.get("low"), t.get("high"), h.get("end")


def _version(c: dict, status: str) -> dict:
    return {k: c.get(k) for k in ("id", "quarter", "quarter_end", "page", "speaker", "quote", "target",
                                  "horizon", "conditional", "scope", "basis", "subject")} | {"status": status}


def _append(th: dict, c: dict) -> None:
    """Same call -> also_said. A version without a number, or the first number for a target-less
    thread, reaffirms; a changed target or deadline revises (old -> new)."""
    last = th["versions"][-1]
    if last["quarter"] == c["quarter"]:
        last.setdefault("also_said", []).append(c["id"])
        return
    prev = effective(th)
    if not has_target(c) or not has_target(prev) or _target_sig(c) == _target_sig(prev):
        th["versions"].append(_version(c, "Reaffirmed"))
    else:
        th["versions"].append(_version(c, "Revised") | {"revised_from": {"target": prev["target"],
                                                                          "horizon": prev["horizon"]}})


def _new(c: dict) -> dict:
    return {"id": c["id"], "metric": c["metric"], "scope": c.get("scope", "company"), "code_linked": code_linked(c),
            "key": _key(c), "versions": [_version(c, "New")]}


RELINK_RATIO = 3.0   # a non-percentage target that jumps >3x is a different subject, not a revision


def _same_key(th: dict, c: dict) -> bool:
    """Same metric and deadline; units must agree when both state a target; INR/unit targets
    more than 3x apart are different things (Rs 1,000 cr vs Rs 150 cr in the same year)."""
    (m, h, u), (m2, h2, u2) = th["key"], _key(c)
    if not (m == m2 and h == h2 and (u is None or u2 is None or u == u2)):
        return False
    a, b = effective(th)["target"], c["target"]
    va, vb = (a.get("high") or a.get("low")), (b.get("high") or b.get("low"))
    return u2 == "pct" or not va or not vb or 1 / RELINK_RATIO <= vb / va <= RELINK_RATIO


def thread(classified_by_call: list[list[dict]], symbol: str, model: str | None = None) -> list[dict]:
    """classified_by_call: per call (oldest first), the commitments that passed the guards."""
    threads: list[dict] = []
    for k, rows in enumerate(classified_by_call):
        llm_new = []
        for c in rows:
            if code_linked(c):
                same = [t for t in threads if t["code_linked"] and _same_key(t, c) and _basis_ok(t, c)]
                if same:
                    _append(same[-1], c)
                    continue
                threads.append(_new(c))
            else:
                llm_new.append(c)
        earlier = [t for t in threads if not t["code_linked"] and t["versions"][-1]["quarter_end"] < rows[0]["quarter_end"]] if rows else []
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
                threads.append(_new(c))
    return threads


def mention_pattern(th: dict) -> re.Pattern:
    """What counts as 'still talked about' in a later call: the metric's words, or the subject's."""
    if th["metric"] in METRIC_WORDS and th.get("scope", "company") == "company":
        return re.compile(METRIC_WORDS[th["metric"]], re.I)
    words = [w for w in re.findall(r"[A-Za-z]{4,}|\b[A-Z]{3}\b", th["versions"][-1].get("subject") or "")
             if w.lower() not in STOP]   # 3-letter acronyms count ("VAM", "VAE")
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
