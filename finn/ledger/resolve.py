"""Stage 4: find the actual for each promise.

Order: XBRL (computed by code from finn.data.financials, with receipts) -> management's own later
statement (model copies the number, code verifies it in the verbatim sentence; "self-reported")
-> unverifiable. For PBDIT the margin is computed with and without other income, and the
definition that matches a figure management itself stated is recorded.
"""
from __future__ import annotations

import json
import math
from datetime import date
from typing import Literal

import pandas as pd
from pydantic import BaseModel

from finn import llm
from finn.data import transcripts as tr
from finn.data.financials import get_quarterly_financials

from .classify import numbers, to_float
from .periods import resolve_horizon, shift
from .thread import effective, has_target, mention_pattern

XBRL_METRICS = ("revenue_growth", "ebitda_margin", "pbdit_margin", "pat")
XBRL_UNITS = {"revenue_growth": ("pct", "inr_cr"), "pat": ("pct", "inr_cr"),   # inr_cr -> summed level
              "pbdit_margin": ("pct", "none"), "ebitda_margin": ("pct", "none")}
MARGIN_DEFS = {"with_other_income": "(pbt + finance_costs + dep_amort) / revenue",
               "without_other_income": "(pbt + finance_costs + dep_amort - other_income) / revenue"}
DEFAULT_DEF = {"pbdit_margin": "with_other_income", "ebitda_margin": "without_other_income"}
MATCH_PP = 0.1      # a computed margin "matches" management's figure within 0.1 percentage point
LEVEL_SANITY = 3.0  # a company-wide INR figure more than 3x away from the target is not what was promised
EVIDENCE_MAX = 12   # sentences shown to the model per promise
BATCH = 6


class Financials:
    """Quarterly XBRL rows per basis, loaded once (cached on disk by finn.data.http)."""

    def __init__(self, symbol: str, n_quarters: int = 16, loader=get_quarterly_financials):
        self.symbol, self.n, self.loader, self._df = symbol, n_quarters, loader, {}

    def df(self, basis: str) -> pd.DataFrame:
        if basis not in self._df:
            d = self.loader(self.symbol, self.n, basis)
            self._df[basis] = d[d["basis"].str.lower() == basis.lower()] if not d.empty else d
        return self._df[basis]

    def latest(self) -> date | None:
        qs = [d["qe"].max() for d in self._df.values() if not d.empty]
        return max(qs) if qs else None


def _rows(df: pd.DataFrame, quarters: list[date]) -> pd.DataFrame | None:
    rows = df[df["qe"].isin(quarters)]
    return rows if len(rows) == len(quarters) and len(quarters) else None


def _receipts(rows: pd.DataFrame, fields: list[str]) -> list[dict]:
    return [{"quarter_end": r["qe"].isoformat(), "field": f, **r["receipts"].get(f, {})}
            for _, r in rows.iterrows() for f in fields]


def compute(metric: str, df: pd.DataFrame, quarters: list[date], unit: str = "pct") -> dict | None:
    """Actual over `quarters` (all must be present). Percentages are in percentage points."""
    rows = _rows(df, quarters)
    if rows is None:
        return None
    s = lambda col, r=rows: float(r[col].sum())
    if metric in ("pbdit_margin", "ebitda_margin"):
        core = s("pbt") + s("finance_costs") + s("dep_amort")
        vals = {"with_other_income": core / s("revenue") * 100,
                "without_other_income": (core - s("other_income")) / s("revenue") * 100}
        return {"values": vals, "formulas": MARGIN_DEFS, "quarters": [q.isoformat() for q in quarters],
                "receipts": _receipts(rows, ["pbt", "finance_costs", "dep_amort", "other_income", "revenue"])}
    if metric in ("revenue_growth", "pat"):
        col = "revenue" if metric == "revenue_growth" else "pat"
        if unit == "inr_cr":
            return {"values": {"level": s(col) / 1e7}, "formulas": {"level": f"sum({col}) / 1e7 (INR crore)"},
                    "quarters": [q.isoformat() for q in quarters], "receipts": _receipts(rows, [col])}
        prior = _rows(df, [shift(q, -4) for q in quarters])
        if prior is None:
            return None
        return {"values": {"yoy": (s(col) / s(col, prior) - 1) * 100},
                "formulas": {"yoy": f"sum({col}) / sum({col}, same quarters a year earlier) - 1"},
                "quarters": [q.isoformat() for q in quarters],
                "receipts": _receipts(rows, [col]) + _receipts(prior, [col])}
    return None


# --- self-reported evidence -----------------------------------------------------------------
class Fact(BaseModel):
    sid: str
    kind: Literal["value", "event_done", "event_delayed"]
    value_text: str
    period_token: str
    basis: Literal["standalone", "consolidated", "unspecified"]


class PromiseFacts(BaseModel):
    promise_id: str
    facts: list[Fact]


class FactsBatch(BaseModel):
    promises: list[PromiseFacts]


FACT_PROMPT = """For each PROMISE made by {symbol} management, look at the EVIDENCE sentences (said by management
in LATER earnings calls) and list only those that report what ACTUALLY happened for the SAME subject as the
promise (same business, product, plant or metric; not merely a similar topic): an achieved figure (kind
"value"), or an explicit statement that the promised event happened (kind "event_done") or was delayed /
did not happen (kind "event_delayed"). Ignore forecasts, targets, hopes and restated promises.
When unsure, return no fact.
- value_text: copy the figure EXACTLY as written in the sentence (e.g. "18.5"), "" for events. Never compute.
- period_token: the period the figure refers to, as Q2FY26 / H1FY26 / FY26, or current_quarter /
  last_quarter if relative to that call (Indian fiscal year: FY26 = April 2025 to March 2026).
- basis: standalone | consolidated | unspecified, only if the sentence says so.
Return facts: [] when no evidence sentence reports an actual. Only use sids that were given.

{items}
"""


def _evidence(th: dict, calls: list[dict], exclude: frozenset = frozenset()) -> list[dict]:
    """Management sentences from calls AFTER the promise was first made (an actual is reported later).
    `exclude`: sentences classified as commitments - a restated promise is not evidence it was kept."""
    first_q = th["versions"][0]["quarter_end"]
    pat = mention_pattern(th)
    numeric = th["metric"] not in ("milestone", "direction", "other")
    ev = [s | {"quarter": c["quarter"], "quarter_end": c["quarter_end"]}
          for c in calls if c["quarter_end"] > first_q for s in c["sentences"]
          if pat.search(s["sentence"]) and (not numeric or numbers(s["sentence"])) and s["sentence"] not in exclude]
    return ev[-EVIDENCE_MAX:]          # latest calls first in importance: keep the most recent


def fact_period(token: str, results_qe: date) -> date | None:
    """Period end of a reported figure. In a results call "this/current/last quarter" and an
    unstated period mean the quarter just reported (unlike a promise's horizon)."""
    t = (token or "").strip().upper()
    if t in ("", "NONE", "CURRENT_QUARTER", "THIS_QUARTER", "LAST_QUARTER"):
        return results_qe
    h = resolve_horizon(token, results_qe)
    return h["end"] if h else None


def self_reported(threads: list[dict], calls: list[dict], symbol: str, model: str | None = None,
                  exclude: frozenset = frozenset()) -> dict[str, list[dict]]:
    """promise id -> verified facts [{sid, quarter, quote, page, speaker, kind, value, period, basis}]."""
    work = [(th, _evidence(th, calls, exclude)) for th in threads]
    work = [(th, ev) for th, ev in work if ev]
    out: dict[str, list[dict]] = {}
    for i in range(0, len(work), BATCH):
        chunk = work[i:i + BATCH]
        items = [{"promise_id": th["id"], "metric": th["metric"], "subject": th["versions"][-1]["subject"],
                  "promise": th["versions"][-1]["quote"],
                  "evidence": [{"sid": s["sid"], "call": s["quarter"], "sentence": s["sentence"]} for s in ev]}
                 for th, ev in chunk]
        res = llm.call("resolve", FACT_PROMPT.format(symbol=symbol, items=json.dumps(items, ensure_ascii=False)),
                       FactsBatch, symbol=symbol, model=model)
        by_sid = {s["sid"]: s for _, ev in chunk for s in ev}
        texts = {c["quarter"]: c["text"] for c in calls}
        for p in res.promises:
            for f in p.facts:
                s = by_sid.get(f.sid)
                if s is None or not tr.verify_quote(s["sentence"], texts[s["quarter"]]):
                    continue
                if f.kind == "value" and (not numbers(f.value_text)
                                          or not set(numbers(f.value_text)) <= set(numbers(s["sentence"]))):
                    continue      # a number the sentence does not contain is discarded
                out.setdefault(p.promise_id, []).append(
                    {"sid": f.sid, "quarter": s["quarter"], "quote": s["sentence"], "page": s["page"],
                     "speaker": s["speaker"], "kind": f.kind, "value": to_float(f.value_text),
                     "period_end": fact_period(f.period_token, s["quarter_end"]), "basis": f.basis})
    return out


# --- resolution -----------------------------------------------------------------------------
def calibrate(facts: list[dict], fin: Financials) -> dict | None:
    """Which (basis, definition) management uses for its margin: the first stated figure that a
    computed margin matches. Pooled across all margin promises of the company."""
    for f in facts:
        if f["kind"] != "value" or f["value"] is None or not f["period_end"]:
            continue
        for b in ([f["basis"]] if f["basis"] != "unspecified" else ["consolidated", "standalone"]):
            got = compute("pbdit_margin", fin.df(b.capitalize()), [f["period_end"]])
            for d, v in (got or {}).get("values", {}).items():
                if abs(round(v, 1) - f["value"]) <= MATCH_PP:
                    return {"basis": b, "definition": d, "fact": f,
                            "note": (f"{b}, {d.replace('_', ' ')}: matches management's stated {f['value']:g}% "
                                     f"for {f['period_end'].isoformat()} ({f['quarter']} p.{f['page']})")}
    return None


def _pick_def(metric: str, facts: list[dict], fin: Financials, basis: str) -> tuple[str, str]:
    """Which margin definition management uses: the one matching a figure they stated."""
    for f in facts:
        if f["kind"] != "value" or f["value"] is None or not f["period_end"]:
            continue
        b = f["basis"] if f["basis"] != "unspecified" else basis
        got = compute(metric, fin.df(b.capitalize()), [f["period_end"]])
        if not got:
            continue
        for d, v in got["values"].items():
            if abs(round(v, 1) - f["value"]) <= MATCH_PP:
                return d, (f"{d.replace('_', ' ')} matches management's stated {f['value']:g}% for "
                           f"{f['period_end'].isoformat()} ({b}), {f['quarter']} p.{f['page']}")
    d = DEFAULT_DEF[metric]
    return d, f"no figure stated by management to calibrate against; default: {d.replace('_', ' ')}"


def resolve(th: dict, facts: list[dict], fin: Financials, as_of_call: date, calib: dict | None = None) -> dict:
    """-> {source: xbrl|self-reported|unverifiable, final, interim, note, ...}.
    `calib` (from calibrate) fixes basis and definition for margin promises that don't state them."""
    v = effective(th)
    h, metric, unit = v["horizon"], th["metric"], v["target"]["unit"]
    res = {"source": "unverifiable", "final": None, "interim": None, "note": None}
    if h is None:
        res["note"] = "open-ended horizon"
        return res
    if xbrl_resolvable(th):
        stated = {x["basis"] for x in th["versions"]} - {"unspecified"}
        margin = metric in DEFAULT_DEF
        bases = (sorted(stated) if stated else
                 [calib["basis"]] if margin and calib else ["consolidated", "standalone"])
        for basis in bases:
            df = fin.df(basis.capitalize())
            if df.empty:
                continue
            if margin and calib:
                dfn, dnote = calib["definition"], calib["note"]
            elif margin:
                dfn, dnote = _pick_def(metric, facts, fin, basis)
            else:
                dfn, dnote = ("level" if unit == "inr_cr" else "yoy"), None
            got = compute(metric, df, h["quarters"], unit)
            done = [q for q in h["quarters"] if q in set(df["qe"])]
            # a year-to-date SUM says nothing about a full-year amount; rates and margins are fine
            part = compute(metric, df, done, unit) if done and not got and unit != "inr_cr" else None
            if v["target"]["kind"] == "direction" and margin:
                got, part = _margin_change(df, h["quarters"], dfn), (_margin_change(df, done, dfn) if done else None)
            target_v = v["target"].get("high") or v["target"].get("low")
            if got and unit == "inr_cr" and target_v and not (1 / LEVEL_SANITY <= got["values"][dfn] / target_v <= LEVEL_SANITY):
                res["note"] = (f"company-wide {metric.split('_')[0]} is {got['values'][dfn]:,.0f} cr vs a target of "
                               f"{target_v:,.0f} cr: the target must refer to a part of the business")
                return res
            if got or part:
                res.update(source="xbrl", basis=basis, definition=dfn, definition_note=dnote,
                           basis_note=None if stated else
                           f"basis not stated; {basis} used" + (" (as calibrated)" if margin and calib else ""))
                if got:
                    res.update(final=got["values"][dfn], detail=got)
                else:
                    res.update(interim=part["values"][dfn], interim_quarters=[q.isoformat() for q in done], detail=part)
                if basis == "consolidated" and not stated:
                    alt = compute(metric, fin.df("Standalone"), h["quarters"] if got else done, unit)
                    if alt:
                        res["standalone_value"] = alt["values"][dfn]
                return res
    # self-reported: the latest verified fact for the promise's period (or within it, as interim)
    numeric = has_target(v) and v["target"]["kind"] in ("value", "range", "direction")
    in_period = [f for f in facts if numeric and f["kind"] == "value" and f["period_end"] in h["quarters"]
                 and plausible(f["value"], v["target"])]
    final = [f for f in in_period if f["period_end"] == h["end"]]
    events = [f for f in facts if f["kind"] in ("event_done", "event_delayed")]
    if metric in ("milestone", "other") and events:      # "demand will improve" is not an event
        f = events[-1]
        return res | {"source": "self-reported", "final": f["kind"], "fact": f}
    if final:
        return res | {"source": "self-reported", "final": final[-1]["value"], "fact": final[-1]}
    if in_period:
        return res | {"source": "self-reported", "interim": in_period[-1]["value"], "fact": in_period[-1]}
    res["note"] = "no XBRL series for this metric and no later management figure found"
    return res


def _margin_change(df: pd.DataFrame, quarters: list[date], dfn: str) -> dict | None:
    """Margin change in percentage points vs the same quarters a year earlier (for "expand margins")."""
    now, before = compute("pbdit_margin", df, quarters), compute("pbdit_margin", df, [shift(q, -4) for q in quarters])
    if not now or not before:
        return None
    return {"values": {dfn: now["values"][dfn] - before["values"][dfn]},
            "formulas": {dfn: f"margin ({MARGIN_DEFS[dfn]}) minus the same quarters a year earlier, in pp"},
            "quarters": now["quarters"], "receipts": now["receipts"] + before["receipts"]}


def plausible(value: float | None, target: dict) -> bool:
    """A reported figure more than 3x away from a non-percentage target is about something else
    (33 million units vs "0.5 million per month"; "1300" vs "3x growth")."""
    t = target.get("high") or target.get("low")
    if value is None or not t or target["unit"] == "pct" or target["kind"] == "direction":
        return value is not None
    return 1 / LEVEL_SANITY <= value / t <= LEVEL_SANITY


def xbrl_resolvable(th: dict) -> bool:
    """Company-wide, a metric XBRL can compute, a unit it can be compared in, and a deadline."""
    v = effective(th)
    return (th["metric"] in XBRL_METRICS and th.get("scope", "company") == "company"
            and v["horizon"] is not None and v["target"]["unit"] in XBRL_UNITS[th["metric"]])
