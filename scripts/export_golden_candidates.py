"""Export forward-looking management sentences from the last N transcripts, for hand-labelling.

    python scripts/export_golden_candidates.py ASIANPAINT DIXON [--n 5]

Writes docs/golden/candidates_<SYM>.csv (label columns left blank) and prints, per call, the
source URL, opening-remarks page span and speaker roles so the labeller can sanity-check them.
High recall by design: FORWARD_BROAD matches "will", "should", "range" etc., number or not.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

from finn.data import http
from finn.data import transcripts as tr

OUT = Path(__file__).resolve().parents[1] / "docs" / "golden"
COLUMNS = ["id", "quarter", "page", "speaker", "sentence",
           "is_promise", "metric", "target", "horizon", "conditional", "notes"]


def fy_label(qe: date) -> str:
    """Indian FY quarter: 2026-03-31 -> Q4FY26, 2026-06-30 -> Q1FY27."""
    q = {6: 1, 9: 2, 12: 3, 3: 4}[qe.month]
    return f"Q{q}FY{(qe.year + (qe.month > 3)) % 100:02d}"


def export(symbol: str, n: int, today: date) -> list[dict]:
    c = http.client()
    found = tr.find_transcripts(symbol, today - timedelta(days=30 * (3 * n + 4)), today, client=c).tail(n)
    calls = []
    with (OUT / f"candidates_{symbol}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        for _, r in found.iterrows():
            q = fy_label(r["quarter_end"])
            parsed = tr.parse_transcript(c.get(r["pdf_url"], policy="permanent").raise_for_status().content)
            rows = tr.management_sentences(parsed)
            for k, s in enumerate(rows, 1):
                w.writerow({"id": f"{symbol}-{q}-{k:03d}", "quarter": q, **s})
            calls.append({"quarter": q, "url": r["pdf_url"], "n": len(rows), "opening": tr.opening_remarks(parsed),
                          "management": parsed["management"], "analysts": parsed["analysts"],
                          "warnings": parsed["warnings"]})
    return calls


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="+")
    ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for sym in a.symbols:
        for call in export(sym, a.n, http.today_ist()):
            print(sym, call)


if __name__ == "__main__":
    main()
