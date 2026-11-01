"""Stage 2: classify candidates (Flash-Lite, batched). The model labels and copies; code checks.

Guards (failures go to `rejected`, never repaired):
  - the quote must be found verbatim in the transcript (tr.verify_quote);
  - every number in the target text must appear in that quote;
  - a value/range target must contain a number.
Horizon tokens are turned into dates by periods.resolve_horizon, not by the model.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel

from finn import llm
from finn.data import transcripts as tr

from .periods import fy_label, resolve_horizon, shift

BATCH = 25
METRICS = ("revenue_growth", "ebitda_margin", "pbdit_margin", "pat", "volume_growth", "capex",
           "order_book", "debt", "milestone", "direction", "other")
Metric = Literal["revenue_growth", "ebitda_margin", "pbdit_margin", "pat", "volume_growth", "capex",
                 "order_book", "debt", "milestone", "direction", "other"]
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


class Target(BaseModel):
    kind: Literal["value", "range", "direction", "none"]
    low_text: str
    high_text: str
    unit: Literal["pct", "inr_cr", "units", "other", "none"]
    comparator: Literal["at_least", "at_most", "about", "range", "up", "down", "none"]


class Item(BaseModel):
    id: str
    metric: Metric
    target: Target
    horizon_token: str
    conditional: bool
    scope: Literal["company", "segment"]
    basis: Literal["standalone", "consolidated", "unspecified"]
    subject: str
    quote: str


class Batch(BaseModel):
    """Non-commitments come back as bare ids: full objects for them were ~80% of output tokens."""
    non_commitment_ids: list[str]
    commitments: list[Item]


PROMPT = """You label sentences from an Indian listed company's earnings call for a "promise ledger".
Company: {symbol}. Results quarter discussed: {quarter}. The call was held during {running}.

A sentence is a commitment only if, at a later date, someone could check
whether it came true: a stated target, range, deadline or milestone, said by management about
the company's own future. Vague hopes ("demand will improve") are NOT commitments, unless a period
is named, in which case use metric "direction". Statements about the past, the industry, remarks about
the call itself ("I will now share...", "we will take questions"), or "we will analyze and tell you"
are NOT commitments.

Examples:
- "...guidance of 18-20% of our PBDIT margins holds" -> commitment, pbdit_margin, range "18" to "20" pct, FY of the call.
- "We expect the JV to start reflecting in our revenues from Q3" -> commitment, milestone, subject "JV revenue starts", Q3 of the current FY.
- "I have not seen the numbers, we will analyze and tell you" -> not a commitment.

Put the id of every sentence that is not a commitment in non_commitment_ids. For each commitment, return
an item in commitments with these fields:
- metric: one of {metrics}.
- target.kind: value | range | direction | none. "from 40 million to 190 million" is a value target of 190
  (the current level is not part of the target); a range is only an explicit band such as "18-20%". low_text/high_text: copy the number(s) EXACTLY as written
  in the sentence (e.g. "18", "20", "1,100"); use "" when there is none. Never compute or convert numbers.
- target.unit: pct | inr_cr | units | other | none. comparator: at_least | at_most | about | range | up | down | none.
- horizon_token: Q1FY27 | H2FY27 | FY28 style when the period is named; or current_quarter | next_quarter |
  current_year | next_year for relative periods; medium_term | long_term if open-ended; none if not stated.
  (Indian fiscal year: FY27 = April 2026 to March 2027.)
- scope: company if it is about the whole listed company's reported figures; segment if it is about a business
  line, product, plant, joint venture, subsidiary, customer or region (e.g. "margin in our mobile business").
- conditional: true if the commitment depends on a stated condition ("if demand holds", "subject to approval").
- basis: standalone | consolidated | unspecified, only if the sentence says so.
- subject: a 2-6 word description of what is promised (for milestones and other).
- quote: the shortest verbatim span of the sentence that contains the commitment (copy exactly).
Every input id must appear exactly once: either in non_commitment_ids or in commitments.

Sentences (JSON; "context" is the preceding sentence, for reference only):
{items}
"""


def numbers(text: str) -> list[str]:
    """Numbers as canonical strings, compared by value: "1,100" -> "1100", "9.0" -> "9"."""
    return [f"{float(n.replace(',', '').rstrip('.')):g}" for n in NUM.findall(text or "")]


def to_float(text: str) -> float | None:
    ns = numbers(text)
    return float(ns[0]) if ns else None


def check(item: Item, cand: dict, call_text: str) -> str | None:
    """Reason to reject a commitment, or None if it passes every guard."""
    quote = item.quote or cand["sentence"]
    if not tr.verify_quote(quote, call_text):
        return "quote not found verbatim in transcript"
    in_quote = set(numbers(quote))
    for t in (item.target.low_text, item.target.high_text):
        missing = [n for n in numbers(t) if n not in in_quote]
        if missing:
            return f"target number(s) {missing} not in quote"
    if item.target.kind in ("value", "range") and to_float(item.target.low_text or item.target.high_text) is None:
        return "value/range target without a number"
    return None


def classify_call(call: dict, model: str | None = None) -> tuple[list[dict], list[dict]]:
    """-> (classified rows for every candidate, rejected rows)."""
    out, rejected = [], []
    cands = call["candidates"]
    for i in range(0, len(cands), BATCH):
        chunk = cands[i:i + BATCH]
        prompt = PROMPT.format(symbol=call["symbol"], quarter=call["quarter"],
                               running=fy_label(shift(call["quarter_end"], 1)), metrics=", ".join(METRICS),
                               items=json.dumps([{"id": c["id"], "speaker": c["speaker"], "context": c["context"],
                                                  "sentence": c["sentence"]} for c in chunk], ensure_ascii=False))
        res = llm.call("classify", prompt, Batch, symbol=call["symbol"], model=model)
        got, negatives = {it.id: it for it in res.commitments}, set(res.non_commitment_ids)
        for c in chunk:
            base = {k: c[k] for k in ("id", "page", "speaker", "sentence")} | {
                "quarter": call["quarter"], "quarter_end": call["quarter_end"]}
            it = got.get(c["id"])
            if it is None:
                if c["id"] not in negatives:
                    rejected.append(base | {"reason": "model returned no label for this id"})
                out.append(base | {"is_commitment": False if c["id"] in negatives else None})
                continue
            row = base | it.model_dump(exclude={"id"}) | {"quote": it.quote or c["sentence"], "is_commitment": True}
            reason = check(it, c, call["text"])
            if reason:
                rejected.append(row | {"reason": reason})
                row["is_commitment"], row["rejected"] = False, reason
            else:
                t = row["target"]
                t["low"], t["high"] = to_float(t["low_text"]), to_float(t["high_text"])
                row["horizon"] = resolve_horizon(it.horizon_token, call["quarter_end"])
            out.append(row)
    return out, rejected
