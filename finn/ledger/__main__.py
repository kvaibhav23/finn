"""python -m finn.ledger ASIANPAINT --quarters 6 [--model gemini-3.5-flash-lite]"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone

from finn import llm
from finn.data import resolve_symbol

from . import render
from .candidates import load_calls
from .classify import classify_call
from .render import target_text
from .resolve import Financials, calibrate, resolve, self_reported, xbrl_resolvable
from .thread import effective, mark_dropped, thread
from .verdict import decide, explain


def utc_now() -> str:
    """Timestamp the site compares with GitHub run times: UTC, explicit 'Z'."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def company_name(symbol: str) -> str | None:
    try:
        return resolve_symbol(symbol)["name"]
    except Exception:  # unknown or delisted symbol: the ledger still says which symbol it is
        return None


def run(symbol: str, quarters: int = 6, model: str | None = None) -> dict:
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    calls = load_calls(symbol, quarters)
    print(f"{symbol}: {len(calls)} calls ({', '.join(c['quarter'] for c in calls)}), "
          f"{sum(len(c['candidates']) for c in calls)} candidate sentences")
    if not calls:
        ledger = {"symbol": symbol, "name": company_name(symbol), "status": "no_transcripts", "generated_at": utc_now(),
                  "message": "No earnings-call transcripts were filed on NSE for this company in the last "
                             f"{quarters} quarters, so there are no promises to check."}
        render.write_status(ledger)
        return ledger
    classified, rejected = [], []
    for c in calls:
        rows, rej = classify_call(c, model)
        classified.append(rows)
        rejected += rej
    commitments = [[r for r in rows if r.get("is_commitment")] for rows in classified]
    print(f"  classify: {sum(map(len, commitments))} commitments, {len(rejected)} rejected by guards")
    threads = thread(commitments, symbol, model)
    fin = Financials(symbol)
    stated = frozenset(r["sentence"] for rows in commitments for r in rows)
    facts = self_reported(threads, calls, symbol, model, exclude=stated)
    margin_facts = [f for th in threads if th["metric"] in ("pbdit_margin", "ebitda_margin")
                    for f in facts.get(th["id"], [])]
    calib = calibrate(margin_facts, fin)
    print(f"  margin definition: {calib['note'] if calib else 'no management figure to calibrate against'}")
    resolutions = {th["id"]: resolve(th, facts.get(th["id"], []), fin, calls[-1]["quarter_end"], calib)
                   for th in threads}
    mark_dropped(threads, calls, xbrl_resolvable)
    as_of = fin.latest()
    explain_facts = []
    for th in threads:
        res = resolutions[th["id"]]
        # non-XBRL promises are judged as of the latest call; XBRL ones as of the latest filing
        when = as_of if xbrl_resolvable(th) else calls[-1]["quarter_end"]
        th["verdict"], th["rule"] = decide(th, res, when)
        last = effective(th)
        val = res.get("final") if res.get("final") is not None else res.get("interim")
        explain_facts.append({"id": th["id"], "promise": last["quote"], "target": target_text(last["target"]),
                              "due": last["horizon"]["end"] if last["horizon"] else "open",
                              "actual": round(val, 2) if isinstance(val, float) else val,
                              "source": res["source"], "verdict": th["verdict"], "rule": th["rule"]})
    lines = explain(explain_facts, symbol, model)
    promises = [{k: v for k, v in th.items() if k != "key"} | {"resolution": resolutions[th["id"]],
                                                               "explanation": lines[th["id"]]} for th in threads]
    ledger = {"symbol": symbol, "name": company_name(symbol), "status": "ok", "generated_at": utc_now(),
              "model": model or llm.ROUTES["classify"],
              "margin_calibration": {k: v for k, v in calib.items() if k != "fact"} if calib else None,
              "as_of_results": as_of, "calls": [{k: c[k] for k in ("quarter", "quarter_end", "pdf_url", "warnings")}
                                               for c in calls],
              "classified": [r for rows in classified for r in rows], "promises": promises, "rejected": rejected,
              "cost": llm.cost_summary(symbol, since=started)}
    js, md = render.write(ledger)
    counts = {}
    for p in promises:
        counts[p["verdict"]] = counts.get(p["verdict"], 0) + 1
    print(f"  {len(promises)} promises: {counts}")
    print(f"  cost this run: ₹{ledger['cost']['total_inr']:.2f} ({ledger['cost']['calls']} calls, "
          f"{ledger['cost']['cached']} cached) -> {js.name}, {md.name}")
    return ledger


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m finn.ledger")
    ap.add_argument("symbol")
    ap.add_argument("--quarters", type=int, default=6)
    ap.add_argument("--model", default=None, help="override the routed model for every stage")
    a = ap.parse_args()
    symbol = a.symbol.upper()
    try:
        run(symbol, a.quarters, a.model)
    except Exception as e:  # the site shows what failed instead of waiting forever
        traceback.print_exc()
        render.write_status({"symbol": symbol, "name": company_name(symbol), "status": "failed",
                             "generated_at": utc_now(),
                             "message": f"The analysis stopped with an error: {type(e).__name__}: {str(e)[:300]}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
