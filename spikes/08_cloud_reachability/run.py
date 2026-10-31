"""Spike 08: are NSE sources reachable from this machine's network?

Same requests and byte-identical headers as spikes 01-07 (imported from spikes/common.py);
only the network differs between environments. One call per check. The only retry: if a
/api/ call gets 401/403, re-warm cookies once per run and repeat that call once. Blocks are
recorded, never worked around.

Deliberately bypasses the data/raw cache (a cache hit would be a false "reachable").

  python spikes/08_cloud_reachability/run.py --env <label>

Output: stdout table, data/reachability/<env>_<utc>.json, a REPORT.md-ready column, and the
GitHub Actions step summary when $GITHUB_STEP_SUMMARY is set. Always exits 0: a block is a result.
"""
import argparse
import json
import os
import platform
import re
import socket
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests

from common import BASE_HEADERS, MIN_INTERVAL, NSE_HOME, ROOT, SITE_HEADERS

IST = timezone(timedelta(hours=5, minutes=30))
TIMEOUT = 20
OUT_DIR = ROOT / "data" / "reachability"
ARCH = "https://nsearchives.nseindia.com"
API = "https://www.nseindia.com/api"
UDIFF = ARCH + "/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
KNOWN_XBRL = ARCH + "/corporate/xbrl/INTEGRATED_FILING_INDAS_1734607_08102026100810_WEB.xml"
KNOWN_PDF = ARCH + "/corporate/kavinavora_31102026173331_SE_31102026_AR.pdf"
GH_VARS = ("RUNNER_OS", "RUNNER_ARCH", "RUNNER_ENVIRONMENT", "GITHUB_RUN_ID", "GITHUB_REPOSITORY")

_last = 0.0


def _throttle() -> None:
    global _last
    wait = MIN_INTERVAL - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()


def session(site: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(BASE_HEADERS)
    s.headers.update(SITE_HEADERS[site])
    return s


def is_json(kind):
    def check(body: bytes) -> bool:
        try:
            d = json.loads(body)
        except ValueError:
            return False
        return isinstance(d, list) if kind == "list" else isinstance(d, dict) and isinstance(d.get("data"), list)
    return check


def probe(s: requests.Session, cid: str, label: str, url: str, params=None, ok_body=None) -> dict:
    full = requests.Request("GET", url, params=params).prepare().url
    rec = {"id": cid, "label": label, "url": full, "status": None, "latency_ms": None, "bytes": None,
           "content_type": None, "server": None, "verdict": None}
    _throttle()
    t0 = time.monotonic()
    try:
        r = s.get(full, timeout=TIMEOUT)
    except requests.Timeout:
        rec |= {"verdict": "TIMEOUT", "latency_ms": int((time.monotonic() - t0) * 1000)}
    except requests.RequestException as e:
        rec |= {"verdict": "CONN_ERR", "latency_ms": int((time.monotonic() - t0) * 1000),
                "head": f"{type(e).__name__}: {e}"[:200]}
    else:
        rec |= {"status": r.status_code, "latency_ms": int((time.monotonic() - t0) * 1000),
                "bytes": len(r.content), "content_type": r.headers.get("Content-Type", "").split(";")[0],
                "server": r.headers.get("Server")}
        if r.status_code == 200:
            rec["verdict"] = "OK" if ok_body is None or ok_body(r.content) else "BAD_BODY"
            if "json" in rec["content_type"]:  # an empty list is weak evidence, so record the count
                try:
                    d = r.json()
                    rec["items"] = len(d) if isinstance(d, list) else len(d.get("data") or [])
                except ValueError:
                    pass
        elif r.status_code == 404:
            rec["verdict"] = "NOT_FOUND"
        elif r.status_code in (401, 403):
            rec["verdict"] = "BLOCKED"
        else:
            rec["verdict"] = f"HTTP_{r.status_code}"
        if rec["verdict"] != "OK":
            rec["head"] = r.content[:200].decode("utf-8", errors="replace")
    print(f"  {cid:10} {str(rec['status'] or '-'):>4} {rec['verdict']:10} {str(rec['latency_ms']) + ' ms':>9} "
          f"{str(rec['bytes'] or '-'):>9} B  {label}"
          + (f"  [{rec['items']} items]" if "items" in rec else ""), flush=True)
    if rec.get("head"):
        print(f"             first 200 bytes: {rec['head']!r}", flush=True)
    return rec


def last_expected_trading_day(now: datetime) -> date:
    d = now.date() if now.hour >= 17 else now.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def prev_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def cell(attempts: list[dict]) -> str:
    """REPORT.md cell for one check, from its final attempt (+ a note if there were several)."""
    f = attempts[-1]
    s = f"{f['status'] or '-'} {f['verdict']}" + (f" · {f['latency_ms']} ms" if f["latency_ms"] is not None else "")
    if "items" in f:
        s += f" · {f['items']} items"
    if len(attempts) > 1:
        s += f" ({len(attempts)} attempts: " + ", ".join(f"{a['status'] or a['verdict']}" for a in attempts) + ")"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=socket.gethostname(), help="label for this environment, e.g. aws-ap-south-1")
    args = ap.parse_args()
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)
    env = {"label": args.env, "platform": platform.platform(), "python": platform.python_version(),
           "requests": requests.__version__, "utc": now_utc.isoformat(timespec="seconds"),
           "ist": now_ist.isoformat(timespec="seconds"),
           **{k: os.environ[k] for k in GH_VARS if k in os.environ}}
    print(f"env: {env}\n")
    plain, nse = session("plain"), session("nse")
    checks = []  # [{"id", "label", "attempts": [...], "rewarm"?}]

    print("a) nsearchives static (plain session, no cookies)")
    checks.append(dict(id="a1", label="EQUITY_L.csv", attempts=[probe(plain, "a1", "EQUITY_L.csv", ARCH + "/content/equities/EQUITY_L.csv",
                                                ok_body=lambda b: b.lstrip().startswith(b"SYMBOL"))]))
    d, bhav = last_expected_trading_day(now_ist), []
    for i in range(5):  # step back over weekends/holidays on 404 only; each step is a different file
        rec = probe(plain, "a2" if i == 0 else f"a2-back{i}", f"UDiFF bhavcopy {d}", UDIFF.format(d=d),
                    ok_body=lambda b: b[:2] == b"PK")
        bhav.append(rec)
        if rec["verdict"] != "NOT_FOUND":
            break
        d = prev_weekday(d)
    checks.append(dict(id="a2", label=f"UDiFF bhavcopy ({bhav[-1]['label'].split()[-1]})", attempts=bhav))
    checks.append(dict(id="a3", label="known XBRL (TCS Q2 FY27)", attempts=[probe(plain, "a3", "known XBRL", KNOWN_XBRL,
                                                            ok_body=lambda b: b"<?xml" in b[:100] or b"xbrl" in b[:2000])]))
    checks.append(dict(id="a4", label="known PDF (RIL 31-Oct-2026)", attempts=[probe(plain, "a4", "known PDF", KNOWN_PDF,
                                                               ok_body=lambda b: b[:5] == b"%PDF-")]))

    print("\nb) www.nseindia.com cookie-gated API (NSE session)")
    warm = probe(nse, "b0", "home page warm-up (recorded only)", NSE_HOME)
    warm["cookies"] = sorted(nse.cookies.keys())
    print(f"             cookies after warm-up: {warm['cookies']}")
    checks.append(dict(id="b0", label="home-page warm-up", attempts=[warm]))

    today = now_ist.date()
    api_calls = [
        ("b1", "corporate-announcements (RELIANCE, 7 days)", "/corporate-announcements",
         {"index": "equities", "symbol": "RELIANCE", "from_date": f"{today - timedelta(days=7):%d-%m-%Y}",
          "to_date": f"{today:%d-%m-%Y}"}, is_json("list")),
        ("b2", "integrated-filing-results (TCS, financials)", "/integrated-filing-results",
         {"index": "equities", "symbol": "TCS", "type": "Integrated Filing- Financials", "page": 1, "size": 20},
         is_json("data")),
        ("b3", "annual-reports (TCS)", "/annual-reports", {"index": "equities", "symbol": "TCS"}, is_json("data")),
    ]
    rewarmed = False
    for cid, label, path, params, ok in api_calls:
        c = {"id": cid, "label": label, "attempts": [probe(nse, cid, label, API + path, params, ok)]}
        if c["attempts"][0]["verdict"] == "BLOCKED" and not rewarmed:  # the single allowed retry per run
            rewarmed = True
            c["rewarm"] = probe(nse, f"{cid}-rewarm", "re-warm (home page)", NSE_HOME)
            c["rewarm"]["cookies"] = sorted(nse.cookies.keys())
            c["attempts"].append(probe(nse, f"{cid}-retry", label + " (after re-warm)", API + path, params, ok))
        checks.append(c)

    # ---- outputs ----
    rows = [f"| {c['id']} | {c['label']} | {cell(c['attempts'])} |" for c in checks]
    table = "\n".join([f"| id | check | {env['label']} |", "|---|---|---|", *rows])
    fails = [(c["id"], a) for c in checks for a in c["attempts"] + [c.get("rewarm") or {}] if a.get("head")]
    excerpts = "\n".join(f"- **{cid}** `{a['status'] or a['verdict']}`: `{a['head'][:200]!r}`" for cid, a in fails)
    print(f"\n== REPORT.md column ({env['label']}, {env['ist']}) ==\n{table}")
    if excerpts:
        print(f"\nfailure excerpts:\n{excerpts}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^\w.-]+", "_", env["label"])  # (no backslash inside f-strings: py<3.12 hosts)
    out = OUT_DIR / f"{safe_label}_{now_utc:%Y%m%dT%H%M%SZ}.json"
    out.write_text(json.dumps({"env": env, "checks": [
        {**c, "final_verdict": c["attempts"][-1]["verdict"]} for c in checks]}, indent=1))
    print(f"\nwrote {out.relative_to(ROOT)}")

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(f"## NSE reachability: {env['label']}\n\n{env['ist']} IST\n\n{table}\n")
            if excerpts:
                fh.write(f"\n### Failure excerpts\n{excerpts}\n")


if __name__ == "__main__":
    main()
