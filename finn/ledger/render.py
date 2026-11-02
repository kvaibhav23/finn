"""Write data/ledger/<SYM>.json and a readable data/ledger/<SYM>.md."""
from __future__ import annotations

import json
from pathlib import Path

from finn import llm

from .thread import effective

OUT = llm.ROOT / "data" / "ledger"
UNIT = {"pct": "%", "inr_cr": " cr"}


def target_text(t: dict | None) -> str:
    if not t or t["kind"] == "none":
        return "—"
    u = UNIT.get(t["unit"], "")
    if t["kind"] == "range":
        return f"{t['low_text']}–{t['high_text']}{u}"
    if t["kind"] == "value":
        pre = {"at_least": "≥ ", "at_most": "≤ ", "about": "~"}.get(t["comparator"], "")
        return f"{pre}{t['low_text'] or t['high_text']}{u}"
    return t["comparator"] if t["comparator"] in ("up", "down") else "direction"


def actual_text(res: dict, unit: str) -> str:
    u = UNIT.get(unit, "")
    val = res.get("final") if res.get("final") is not None else res.get("interim")
    if res["source"] == "xbrl" and val is not None:
        url = (res.get("detail", {}).get("receipts") or [{}])[-1].get("xbrl_url", "")
        tag = "" if res.get("final") is not None else f" YTD {len(res.get('interim_quarters', []))}q"
        defn = f", {res['definition'].replace('_', ' ')}" if res.get("definition") in ("with_other_income", "without_other_income") else ""
        return f"{val:.2f}{u}{tag} (XBRL, {res['basis']}{defn}) [src]({url})"
    if res["source"] == "self-reported":
        f = res["fact"]
        shown = f["kind"].replace("_", " ") if isinstance(val, str) else f"{val:g}{u}"
        return f"{shown} (self-reported, {f['quarter']} p.{f['page']})"
    return "—"


def _due(h: dict | None) -> str:
    if not h:
        return "open"
    end = h["end"] if isinstance(h["end"], str) else h["end"].isoformat()
    return end + (" (assumed)" if h.get("assumed") else "")


def _change(v: dict) -> str:
    old, new = target_text(v["revised_from"]["target"]), target_text(v["target"])
    return f"{old} → {new}" if old != new else f"due {_due(v['revised_from']['horizon'])} → {_due(v['horizon'])}"


def write_status(ledger: dict) -> Path:
    """A ledger with no promises (no transcripts, or a failed run): JSON + a one-line markdown."""
    OUT.mkdir(parents=True, exist_ok=True)
    js = OUT / f"{ledger['symbol']}.json"
    js.write_text(json.dumps(ledger, indent=1, ensure_ascii=False, default=str))
    (OUT / f"{ledger['symbol']}.md").write_text(f"# {ledger['symbol']}: promise ledger\n\n{ledger['message']}\n")
    return js


def write(ledger: dict) -> tuple[Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    sym = ledger["symbol"]
    js = OUT / f"{sym}.json"
    js.write_text(json.dumps(ledger, indent=1, ensure_ascii=False, default=str))
    lines = [f"# {sym}: promise ledger", "",
             f"Calls: {', '.join(c['quarter'] for c in ledger['calls'])} · generated {ledger['generated_at']} · "
             f"model {ledger['model']} · cost this run ₹{ledger['cost']['total_inr']:.2f} "
             f"({ledger['cost']['calls']} model calls, {ledger['cost']['cached']} cached)", "",
             *([f"Margin definition: {ledger['margin_calibration']['note']}", ""] if ledger.get("margin_calibration") else []),
             "| # | Promise (verbatim) | Made | Target | Due | Actual | Verdict | Why |",
             "|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(ledger["promises"], 1):
        first, last = p["versions"][0], effective(p)
        hist = "; ".join(f"{v['status']} {v['quarter']}" + (f" ({_change(v)})" if v["status"] == "Revised" else "")
                         for v in p["versions"][1:])
        quote = last["quote"].replace("|", "/")
        cell = f"“{quote}” — {last['speaker']}, {last['quarter']} p.{last['page']}" + (f"<br>{hist}" if hist else "")
        due = _due(last["horizon"])
        cond = " (conditional)" if last["conditional"] else ""
        lines.append(f"| {i} | {cell} | {first['quarter']} | {target_text(last['target'])}{cond} | {due} | "
                     f"{actual_text(p['resolution'], last['target']['unit'])} | **{p['verdict']}** | {p['explanation']} |")
    lines += ["", f"Rejected by guards: {len(ledger['rejected'])} (see JSON). "
              "Numbers come from XBRL or verbatim management quotes; verdicts are code rules."]
    md = OUT / f"{sym}.md"
    md.write_text("\n".join(lines) + "\n")
    return js, md
