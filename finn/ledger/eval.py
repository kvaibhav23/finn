"""python -m finn.ledger.eval -> precision / recall against docs/golden/candidates_<SYM>.csv + cost.

Joins on id, but only when the sentence text also matches (guards against id drift if the parser
changes); otherwise, and for rows you added by hand, by verbatim containment within the quarter.
Recall misses are split: "candidate filter" (the engine never saw the sentence) vs "classifier".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from finn import llm
from finn.data.text import canonical

from .render import OUT as LEDGER_DIR

GOLDEN_DIR = llm.ROOT / "docs" / "golden"


def _yes(v: str) -> bool:
    return str(v).strip().upper() in ("Y", "YES", "1", "TRUE")


def _match(row: pd.Series, by_id: dict, by_quarter: dict) -> dict | None:
    r = by_id.get(row["id"].strip())
    if r is not None and canonical(r["sentence"]) == canonical(row["sentence"]):
        return r
    g = canonical(row["sentence"])
    return next((r for r in by_quarter.get(row["quarter"].strip(), [])
                 if g and (g in canonical(r["sentence"]) or canonical(r["sentence"]) in g)), None)


def evaluate(golden: Path, ledger: Path) -> dict:
    g = pd.read_csv(golden, dtype=str, keep_default_na=False)
    lab = g[g["is_promise"].str.strip() != ""]
    out = {"symbol": golden.stem.replace("candidates_", ""), "rows": len(g), "labelled": len(lab)}
    if lab.empty or not ledger.exists():
        return out | {"ledger_missing": not ledger.exists()}
    L = json.loads(ledger.read_text())
    covered = {c["quarter"] for c in L["calls"]}
    by_id = {r["id"]: r for r in L["classified"]}
    by_quarter: dict[str, list] = {}
    for r in L["classified"]:
        by_quarter.setdefault(r["quarter"], []).append(r)
    tp = fp = fn_filter = fn_classifier = metric_ok = metric_n = skipped = 0
    misses = []
    for _, row in lab.iterrows():
        if row["quarter"].strip() not in covered:
            skipped += 1
            continue
        gold, r = _yes(row["is_promise"]), _match(row, by_id, by_quarter)
        pred = bool(r and r.get("is_commitment"))
        if gold and pred:
            tp += 1
            if row["metric"].strip():
                metric_n += 1
                metric_ok += row["metric"].strip() == r.get("metric")
        elif pred:
            fp += 1
        elif gold:
            if r is None:
                fn_filter += 1
            else:
                fn_classifier += 1
            misses.append({"id": row["id"], "stage": "candidate filter" if r is None else "classifier",
                           "sentence": row["sentence"][:120]})
    fn = fn_filter + fn_classifier
    return out | {
        "skipped_quarters_not_in_ledger": skipped, "tp": tp, "fp": fp, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
        "missed_at_candidate_filter": fn_filter, "missed_at_classifier": fn_classifier,
        "metric_agreement": metric_ok / metric_n if metric_n else None, "misses": misses,
        "cost_inr_all_runs": llm.cost_summary(out["symbol"])["total_inr"]}


def main(golden_dir: Path = GOLDEN_DIR, ledger_dir: Path = LEDGER_DIR) -> int:
    files = sorted(golden_dir.glob("candidates_*.csv"))
    if not files:
        print(f"no golden files in {golden_dir}")
        return 0
    results = [evaluate(f, ledger_dir / f"{f.stem.replace('candidates_', '')}.json") for f in files]
    if not any(r["labelled"] for r in results):
        print("golden set not labelled yet: fill is_promise (Y/N) in " + ", ".join(f.name for f in files))
        return 0
    pct = lambda x: "—" if x is None else f"{x:.0%}"
    print(f"{'symbol':<12}{'labelled':>9}{'precision':>11}{'recall':>8}{'TP':>5}{'FP':>5}{'FN':>5}"
          f"{'miss@filter':>13}{'miss@clf':>10}{'metric':>8}{'₹ total':>9}")
    for r in results:
        if not r["labelled"] or r.get("ledger_missing"):
            print(f"{r['symbol']:<12}{r['labelled']:>9}  " + ("no ledger: run python -m finn.ledger " + r["symbol"]
                                                             if r.get("ledger_missing") else "not labelled"))
            continue
        print(f"{r['symbol']:<12}{r['labelled']:>9}{pct(r['precision']):>11}{pct(r['recall']):>8}{r['tp']:>5}"
              f"{r['fp']:>5}{r['fn']:>5}{r['missed_at_candidate_filter']:>13}{r['missed_at_classifier']:>10}"
              f"{pct(r['metric_agreement']):>8}{r['cost_inr_all_runs']:>9.2f}")
        for m in r["misses"][:10]:
            print(f"    missed ({m['stage']}): {m['id'] or '(added)'} {m['sentence']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
