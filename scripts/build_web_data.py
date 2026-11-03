"""Build the website's data: web/public/data/{symbols,index}.json + ledgers/<SYM>.json + market/<SYM>.json.

    python scripts/build_web_data.py            # all ledgers in data/ledger/
    python scripts/build_web_data.py --symbols  # also refresh the NSE symbol list (1 request, cached daily)

The site never parses pipeline internals: this script writes a small, display-ready shape.
Titles are built by code from the metric and the copied target text; the model's short subject
phrase is used only for milestones / segment promises, and only if every number in it is in the quote.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from finn.ledger.classify import numbers
from finn.ledger.render import target_text
from finn.ledger.thread import effective

ROOT = Path(__file__).resolve().parents[1]
LEDGERS = ROOT / "data" / "ledger"
MARKET = ROOT / "data" / "market"
OUT = ROOT / "web" / "public" / "data"

METRIC_LABEL = {"revenue_growth": "Revenue growth", "ebitda_margin": "EBITDA margin", "pbdit_margin": "PBDIT margin",
                "pat": "Profit after tax", "volume_growth": "Volume growth", "capex": "Capex",
                "order_book": "Order book", "debt": "Debt", "milestone": "Milestone", "direction": "Direction",
                "other": "Other"}
ORDER = ["Kept", "Missed", "On track", "Revised", "Pending", "Dropped", "Unverifiable"]
UNIT = {"pct": "%", "inr_cr": " cr"}


def _iso(d) -> str | None:
    return None if d is None else str(d)[:10]


def excerpt(quote: str, words: int = 9) -> str:
    """The speaker's own opening words, when no better title exists ("Milestone" says nothing)."""
    w = quote.strip().strip("“”\"").split()
    text = " ".join(w[:words]) + ("…" if len(w) > words else "")
    return text[:1].upper() + text[1:]


def title(p: dict, v: dict) -> str:
    label = METRIC_LABEL.get(p["metric"], "Other")
    subject = (v.get("subject") or "").strip()
    if subject and not set(numbers(subject)) <= set(numbers(v["quote"])):
        subject = ""                                     # a number the speaker never said
    t = v.get("target") or {"kind": "none", "unit": "none"}
    # only %, crore figures read correctly out of context; "10" for "10 lakh people" does not
    tgt = target_text(t) if t["kind"] in ("value", "range") and t["unit"] in ("pct", "inr_cr") else ""
    vague = p["metric"] in ("milestone", "other", "direction")
    if subject and (vague or p.get("scope") == "segment"):
        head = subject[:1].upper() + subject[1:]
    else:
        head = excerpt(v["quote"]) if vague else label
    return f"{head} {tgt}".strip()


MARGINS = ("pbdit_margin", "ebitda_margin")


def actual(res: dict, unit: str, metric: str = "", pdf: dict | None = None) -> dict | None:
    val = res.get("final") if res.get("final") is not None else res.get("interim")
    u = "%" if metric in MARGINS else UNIT.get(unit, "")
    if res["source"] == "xbrl" and isinstance(val, (int, float)):
        receipts = (res.get("detail") or {}).get("receipts") or []
        defn = res.get("definition")
        return {"source": "XBRL filing", "value": round(val, 2), "text": f"{val:,.2f}{u}",
                "partial": res.get("final") is None, "quarters": res.get("interim_quarters"),
                "basis": res.get("basis"), "definition": defn.replace("_", " ") if defn in (
                    "with_other_income", "without_other_income") else None,
                "formula": ((res.get("detail") or {}).get("formulas") or {}).get(defn),
                "link": receipts[-1].get("xbrl_url") if receipts else None,
                "note": res.get("definition_note") or res.get("basis_note")}
    if res["source"] == "self-reported":
        f = res["fact"]
        text = {"event_done": "Reported done", "event_delayed": "Reported delayed"}.get(val, None) \
            if isinstance(val, str) else f"{val:g}{u}"
        return {"source": "Management, later call", "value": val if not isinstance(val, str) else None,
                "text": text, "partial": res.get("final") is None, "quote": f["quote"], "quarter": f["quarter"],
                "page": f["page"], "speaker": f["speaker"], "pdf_url": (pdf or {}).get(f["quarter"])}
    return None


def slim(L: dict) -> dict:
    base = {k: L.get(k) for k in ("symbol", "name", "status", "message", "generated_at")}
    if L.get("status", "ok") != "ok":
        return base | {"promises": [], "calls": []}
    pdf = {c["quarter"]: c["pdf_url"] for c in L["calls"]}
    promises = []
    for p in L["promises"]:
        v, first = effective(p), p["versions"][0]
        h = v.get("horizon")
        promises.append({
            "id": p["id"], "metric": p["metric"], "metric_label": METRIC_LABEL.get(p["metric"], "Other"),
            "scope": p.get("scope", "company"), "title": title(p, v), "target": target_text(v["target"]),
            "conditional": bool(v.get("conditional")), "due": _iso(h["end"]) if h else None,
            "due_assumed": bool(h and h.get("assumed")), "verdict": p["verdict"], "rule": p["rule"],
            "explanation": p["explanation"], "first_quarter": first["quarter"],
            "quote": v["quote"], "speaker": v["speaker"], "quarter": v["quarter"], "page": v["page"],
            "pdf_url": pdf.get(v["quarter"]),
            "history": [{"quarter": x["quarter"], "status": x["status"], "quote": x["quote"], "page": x["page"],
                         "speaker": x["speaker"], "pdf_url": pdf.get(x["quarter"]), "target": target_text(x["target"]),
                         "due": _iso((x.get("horizon") or {}).get("end"))} for x in p["versions"]],
            "searched_later": p.get("searched_later", []),
            "actual": actual(p["resolution"], v["target"]["unit"] if v.get("target") else "none", p["metric"], pdf),
        })
    promises.sort(key=lambda x: (ORDER.index(x["verdict"]) if x["verdict"] in ORDER else 99, x["due"] or "9999"))
    calib = L.get("margin_calibration") or {}
    return base | {
        "as_of_results": _iso(L.get("as_of_results")), "model": L.get("model"),
        "cost_inr": round(L.get("cost", {}).get("total_inr", 0.0), 2),
        "calls": [{"quarter": c["quarter"], "quarter_end": _iso(c["quarter_end"]), "pdf_url": c["pdf_url"]}
                  for c in L["calls"]],
        "margin_note": calib.get("note"), "candidates": len(L.get("classified", [])),
        "rejected": len(L.get("rejected", [])), "promises": promises}


def counts(promises: list[dict]) -> dict:
    c = {k: 0 for k in ORDER}
    for p in promises:
        c[p["verdict"]] = c.get(p["verdict"], 0) + 1
    return c


def slim_market(m: dict) -> dict:
    """What the page shows. The summary and signal sentences are written by the site (web/lib/sentences.ts),
    from these facts, in the reader's language."""
    keep = ("symbol", "generated_at", "price", "prices", "nifty", "results", "filings", "calls", "signals", "move")
    return {k: m.get(k) for k in keep} | {"missing": sorted((m.get("errors") or {}).keys())}


def market_banner(market_dir: Path, index: list[dict], top: int = 3) -> dict | None:
    """The Nifty 50's last day and the tracked companies that moved most that day."""
    f = market_dir / "_market.json"
    if not f.exists():
        return None
    day = json.loads(f.read_text())
    same_day = [i for i in index if i.get("price_as_of") == day["date"] and i.get("change_pct") is not None]
    movers = sorted(same_day, key=lambda i: -abs(i["change_pct"]))[:top]
    return day | {"movers": [{"symbol": i["symbol"], "name": i["name"], "change_pct": i["change_pct"]} for i in movers]}


def build(ledger_dir: Path = LEDGERS, out: Path = OUT, market_dir: Path = MARKET) -> list[dict]:
    (out / "ledgers").mkdir(parents=True, exist_ok=True)
    (out / "market").mkdir(parents=True, exist_ok=True)
    sym_file = out / "symbols.json"
    names = dict(json.loads(sym_file.read_text())) if sym_file.exists() else {}
    index = []
    for f in sorted(ledger_dir.glob("*.json")):
        if f.name == "cost_log.jsonl":
            continue
        L = json.loads(f.read_text())
        if "symbol" not in L:
            continue
        s = slim(L | {"status": L.get("status", "ok"), "name": L.get("name") or names.get(L["symbol"])})
        (out / "ledgers" / f"{s['symbol']}.json").write_text(json.dumps(s, ensure_ascii=False, separators=(",", ":")))
        calls = s["calls"]
        mf = market_dir / f"{s['symbol']}.json"
        price = None
        if mf.exists():
            mk = slim_market(json.loads(mf.read_text()))
            (out / "market" / mf.name).write_text(json.dumps(mk, ensure_ascii=False, separators=(",", ":")))
            price = mk.get("price")
        index.append({"symbol": s["symbol"], "name": s["name"], "status": s["status"],
                      "generated_at": s["generated_at"], "as_of_results": s.get("as_of_results"),
                      "calls": len(calls), "from": calls[0]["quarter"] if calls else None,
                      "to": calls[-1]["quarter"] if calls else None, "promises": len(s["promises"]),
                      "counts": counts(s["promises"]),
                      "close": (price or {}).get("close"), "change_pct": (price or {}).get("change_pct"),
                      "price_as_of": (price or {}).get("as_of"),
                      "return_1y": (price or {}).get("return_1y"),
                      "big_move": bool(mf.exists() and json.loads(mf.read_text()).get("move"))})
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))
    banner = market_banner(market_dir, index)
    (out / "market.json").write_text(json.dumps(banner, ensure_ascii=False, indent=1))
    return index


def build_symbols(out: Path = OUT) -> int:
    from finn.data.symbols import load_master
    m = load_master()
    out.mkdir(parents=True, exist_ok=True)
    rows = sorted([r["SYMBOL"], r["NAME OF COMPANY"]] for _, r in m.iterrows())
    (out / "symbols.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", action="store_true", help="refresh web/public/data/symbols.json from NSE")
    a = ap.parse_args()
    if a.symbols:
        print(f"symbols.json: {build_symbols()} NSE symbols")
    idx = build()
    print(f"index.json: {len(idx)} companies: " + ", ".join(f"{i['symbol']} ({i['promises']})" for i in idx))


if __name__ == "__main__":
    main()
