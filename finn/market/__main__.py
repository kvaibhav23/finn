"""Market data for company pages: prices, key numbers, filings and signals -> data/market/<SYM>.json.

    python -m finn.market TCS ASIANPAINT        # named companies
    python -m finn.market --ledgers             # every company with a ledger (the nightly job)
    python -m finn.market --ledgers --stale     # also print companies whose ledger needs a rerun
    python -m finn.market --portfolio --ledgers # the portfolio plus every ledger company (the daily job)

No model is called, except to lay out a new appointee's profile that code has already found in the filing
(finn/market/people.py; cached, and skipped without a key). One company failing (NSE hiccup) does not stop the others; its file keeps the
error so the site can leave that section out.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from finn.data import http
from finn.data.corporate_actions import get_corporate_actions
from finn.data.financials import get_quarterly_financials
from finn.data.transcripts import candidates, quarter_for
from finn.portfolio import PORTFOLIO

from . import filings as filings_mod
from .people import add_profiles
from .moves import big_move, events, market_day
from .prices import SOURCE, adjust, history
from .signals import signals
from .stats import price_stats, results_stats

ROOT = Path(__file__).resolve().parents[2]
LEDGERS = ROOT / "data" / "ledger"
OUT = ROOT / "data" / "market"


def ledger_symbols(ledger_dir: Path = LEDGERS) -> list[str]:
    return sorted(f.stem for f in ledger_dir.glob("*.json"))


def read_ledger(symbol: str, ledger_dir: Path = LEDGERS) -> dict | None:
    f = ledger_dir / f"{symbol}.json"
    return json.loads(f.read_text()) if f.exists() else None


def verdict_counts(L: dict | None) -> dict | None:
    if not L or L.get("status", "ok") != "ok":
        return None
    c: dict[str, int] = {}
    for p in L.get("promises", []):
        c[p["verdict"]] = c.get(p["verdict"], 0) + 1
    return c


def needs_rerun(L: dict | None, ann: pd.DataFrame, latest_results_qe: str | None) -> str | None:
    """Why a ledger is out of date, or None: a transcript for a later quarter was filed, or later results."""
    if not L or L.get("status", "ok") != "ok" or not L.get("calls"):
        return None
    last_call = date.fromisoformat(str(L["calls"][-1]["quarter_end"])[:10])
    if not ann.empty:
        t = candidates(ann)
        t = t[t["subject"].str.contains("transcript", case=False, na=False) & t["filed_at"].notna()]
        later = [quarter_for(d.date()) for d in t["filed_at"] if quarter_for(d.date()) > last_call]
        if later:
            return f"earnings call transcript for the quarter ended {max(later).isoformat()}"
    as_of = L.get("as_of_results")
    if latest_results_qe and as_of and latest_results_qe > str(as_of)[:10]:
        return f"results for the quarter ended {latest_results_qe}"
    return None


def build_one(symbol: str, rows: list[dict], nifty: list[dict], end: date,
              client: http.Client, ledger_dir: Path = LEDGERS) -> dict:
    out: dict = {"symbol": symbol, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "errors": {}}
    try:
        actions = get_corporate_actions(symbol, client)
    except Exception as e:                       # noqa: BLE001 - the page can live without adjustments
        actions, out["errors"]["corporate_actions"] = None, f"{type(e).__name__}: {e}"
    rows, applied = adjust(rows, actions)
    price = price_stats(rows, nifty)
    out["price"] = price
    out["prices"] = {"source": SOURCE, "adjusted_for": applied,
                     "rows": [[r["date"].isoformat(), round(r["close"], 2), r["volume"],
                               None if r["deliv_pct"] is None else round(r["deliv_pct"], 2)] for r in rows]}
    out["nifty"] = [[n["date"].isoformat(), n["close"]] for n in nifty]

    try:
        fin = get_quarterly_financials(symbol, 9, client=client)
        out["results"] = results_stats(fin, actions, price["close"] if price else None)
    except Exception as e:                       # noqa: BLE001
        out["results"], out["errors"]["results"] = None, f"{type(e).__name__}: {e}"

    ann = pd.DataFrame()
    try:
        ann = filings_mod.get_announcements_for(symbol, end, client)
        out["filings"] = filings_mod.recent(filings_mod.within(ann, end))
        out["routine"] = filings_mod.routine_times(filings_mod.within(ann, end, 30))
        try:
            add_profiles(symbol, out["filings"], client, (end - timedelta(days=30)).isoformat())
        except Exception as e:                   # noqa: BLE001 - profiles are extra; the filings stand without them
            out["errors"]["profiles"] = f"{type(e).__name__}: {e}"
        out["calls"] = filings_mod.call_dates(ann)
    except Exception as e:                       # noqa: BLE001
        out["filings"], out["errors"]["filings"] = None, f"{type(e).__name__}: {e}"

    L = read_ledger(symbol, ledger_dir)
    counts = verdict_counts(L)
    out["move"] = big_move(rows, out["filings"], nifty)
    out["signals"] = signals(price, counts, out["filings"], filings_mod.DAYS, out["move"])
    out["rerun"] = needs_rerun(L, ann, (out.get("results") or {}).get("latest_qe"))
    out["ledger_generated_at"], out["ledger_counts"] = (L or {}).get("generated_at"), counts
    return out


def read_previous(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def run(symbols: list[str], end: date | None = None, out_dir: Path = OUT, ledger_dir: Path = LEDGERS,
        client: http.Client | None = None) -> list[dict]:
    c = client or http.client()
    end = end or c.today()
    rows, nifty = history(symbols, end, client=c)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = market_day(nifty)
    if day:
        (out_dir / "_market.json").write_text(json.dumps(day, indent=1))
    built = []
    for s in symbols:
        path = out_dir / f"{s}.json"
        before = read_previous(path)
        try:
            m = build_one(s, rows.get(s, []), nifty, end, c, ledger_dir)
            m["events"] = events(s, m, before)
        except Exception as e:                   # noqa: BLE001 - one company must not stop the night's run
            traceback.print_exc()
            m = (before or {"symbol": s}) | {"errors": {"build": f"{type(e).__name__}: {e}"}, "events": []}
        path.write_text(json.dumps(m, ensure_ascii=False, indent=1, default=str))
        built.append(m)
    return built


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m finn.market")
    ap.add_argument("symbols", nargs="*")
    ap.add_argument("--ledgers", action="store_true", help="every company in data/ledger/")
    ap.add_argument("--portfolio", action="store_true", help="every company in finn/portfolio.py")
    ap.add_argument("--stale", action="store_true", help="print 'SYMBOL<TAB>reason' for ledgers needing a rerun")
    ap.add_argument("--end", type=date.fromisoformat, help="last day (default: today, IST)")
    a = ap.parse_args(argv)
    symbols = sorted(set(s.upper() for s in a.symbols) | (set(ledger_symbols()) if a.ledgers else set())
                     | (set(PORTFOLIO) if a.portfolio else set()))
    if not symbols:
        ap.error("name at least one symbol, or pass --ledgers or --portfolio")
    built = run(symbols, a.end)
    for m in built:
        p, err = m.get("price"), m.get("errors") or {}
        print(f"{m['symbol']}: " + (f"close {p['close']:,.2f} on {p['as_of']}" if p else "no prices")
              + (f"; errors: {', '.join(err)}" if err else ""), file=sys.stderr)
    if a.stale:
        for m in built:
            if m.get("rerun"):
                print(f"{m['symbol']}\t{m['rerun']}")


if __name__ == "__main__":
    main()
