"""Hand this run's alert events to the website, which sends them to confirmed subscribers.

    python scripts/send_alerts.py            # every company's data/market/<SYM>.json "events"
    python scripts/send_alerts.py TCS        # only these companies (the ledger workflow)

Needs FINN_SITE_URL and ALERTS_SECRET in the environment; without them it says so and does nothing,
so the workflow works before alerts are set up. The site skips events it has already sent.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "market"


def collect(market_dir: Path = MARKET, symbols: list[str] | None = None) -> list[dict]:
    out = []
    for f in sorted(market_dir.glob("*.json")):
        if f.name.startswith("_") or (symbols and f.stem not in symbols):
            continue
        out.extend(json.loads(f.read_text()).get("events") or [])
    return out


def main() -> int:
    events = collect(symbols=[a.upper() for a in sys.argv[1:]] or None)
    site, secret = os.environ.get("FINN_SITE_URL", "").rstrip("/"), os.environ.get("ALERTS_SECRET", "")
    print(f"{len(events)} alert event(s): " + ", ".join(f"{e['symbol']} {e['kind']}" for e in events))
    if not events:
        return 0
    if not site or not secret:
        print("FINN_SITE_URL or ALERTS_SECRET not set: alerts are not switched on yet")
        return 0
    r = requests.post(f"{site}/api/alerts/dispatch", json={"events": events},
                      headers={"Authorization": f"Bearer {secret}"}, timeout=280)
    print(f"dispatch: HTTP {r.status_code} {r.text[:300]}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
