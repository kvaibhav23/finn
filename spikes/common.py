"""Shared polite HTTP + disk cache for FINN spikes.

- One requests.Session per site, realistic browser headers.
- Every successful response is cached in data/raw/ keyed by sha256(full URL);
  a cached URL is never fetched again.
- At most one live request per MIN_INTERVAL seconds, across all sites.
- Failures are returned (not raised) so spikes can report them.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

MIN_INTERVAL = 1.1  # seconds between live requests
TIMEOUT = 30

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",  # no br: requests can't decode it without extra deps
    "Connection": "keep-alive",
}
SITE_HEADERS = {
    "nse": {"Referer": "https://www.nseindia.com/"},
    "bse": {
        "Referer": "https://www.bseindia.com/",
        "Origin": "https://www.bseindia.com",
        "Sec-Fetch-Site": "same-site",
    },
    "plain": {},
}
NSE_HOME = "https://www.nseindia.com/"

REQUEST_LOG: list[dict] = []  # one entry per fetch (live or cache), for reports
_last_live = 0.0
_sessions: dict[str, requests.Session] = {}

EXT_BY_TYPE = {
    "application/json": ".json",
    "text/html": ".html",
    "text/csv": ".csv",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/xml": ".xml",
    "text/xml": ".xml",
}


@dataclass
class Fetched:
    url: str
    status: int | None
    content: bytes | None
    content_type: str
    latency_ms: int | None
    cached: bool
    error: str | None = None
    path: Path | None = None

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.content is not None

    def json(self):
        return json.loads(self.content)

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding, errors="replace")


def make_session(site: str = "plain") -> requests.Session:
    """Return the shared session for 'nse', 'bse' or 'plain'."""
    if site not in _sessions:
        s = requests.Session()
        s.headers.update(BASE_HEADERS)
        s.headers.update(SITE_HEADERS[site])
        s.site = site
        s.warmed = False
        _sessions[site] = s
    return _sessions[site]


def full_url(url: str, params: dict | None = None) -> str:
    return requests.Request("GET", url, params=params).prepare().url


def _throttle() -> None:
    global _last_live
    wait = MIN_INTERVAL - (time.monotonic() - _last_live)
    if wait > 0:
        time.sleep(wait)
    _last_live = time.monotonic()


def _log(kind: str, status, latency_ms, url: str, nbytes=None, error=None) -> None:
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "kind": kind,
        "status": status,
        "latency_ms": latency_ms,
        "bytes": nbytes,
        "url": url,
        "error": error,
    }
    REQUEST_LOG.append(entry)
    lat = f"{latency_ms}ms" if latency_ms is not None else "-"
    extra = f" ERR={error}" if error else ""
    print(f"{entry['at'][11:23]} {kind:5} {status} {lat:>7} {url[:110]}{extra}", flush=True)


def _warm_nse(session: requests.Session) -> None:
    """NSE's API wants cookies set by a normal page visit first. Not cached."""
    _throttle()
    t0 = time.monotonic()
    try:
        r = session.get(NSE_HOME, timeout=TIMEOUT)
        _log("WARM", r.status_code, int((time.monotonic() - t0) * 1000), NSE_HOME, len(r.content))
    except requests.RequestException as e:
        _log("WARM", None, None, NSE_HOME, error=type(e).__name__)
    session.warmed = True


def _meta_path(key: str) -> Path:
    return RAW / f"{key}.meta.json"


def fetch(session: requests.Session, url: str, *, params: dict | None = None,
          warm: bool = True, cache_404: bool = False) -> Fetched:
    """GET url, from cache if we've ever fetched it successfully.

    cache_404: also cache a 404 (only for immutable URLs, e.g. a past date's
    archive file that will never appear, like a holiday's bhavcopy).
    """
    url = full_url(url, params)
    key = hashlib.sha256(url.encode()).hexdigest()[:20]
    meta_file = _meta_path(key)

    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
        body = RAW / meta["file"]
        _log("CACHE", meta["status"], meta["latency_ms"], url, meta["bytes"])
        return Fetched(url, meta["status"], body.read_bytes(), meta["content_type"],
                       meta["latency_ms"], cached=True, path=body)

    if session.site == "nse" and warm and not session.warmed:
        _warm_nse(session)

    _throttle()
    t0 = time.monotonic()
    try:
        r = session.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        _log("LIVE", None, None, url, error=type(e).__name__)
        return Fetched(url, None, None, "", None, cached=False, error=f"{type(e).__name__}: {e}")
    latency = int((time.monotonic() - t0) * 1000)
    ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    _log("LIVE", r.status_code, latency, url, len(r.content))

    if r.status_code != 200 and not (cache_404 and r.status_code == 404):  # never cache failures
        return Fetched(url, r.status_code, r.content, ctype, latency, cached=False,
                       error=f"HTTP {r.status_code}")

    suffix = Path(url.split("?")[0]).suffix.lower()
    ext = suffix if suffix in {".csv", ".zip", ".pdf", ".xml", ".json", ".txt"} else EXT_BY_TYPE.get(ctype, ".bin")
    body = RAW / f"{key}{ext}"
    body.write_bytes(r.content)
    meta_file.write_text(json.dumps({
        "url": url, "status": r.status_code, "content_type": ctype,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latency_ms": latency, "bytes": len(r.content), "file": body.name,
        "last_modified": r.headers.get("Last-Modified"),
    }, indent=1))
    return Fetched(url, r.status_code, r.content, ctype, latency, cached=False, path=body)


def cached_meta(url: str, params: dict | None = None) -> dict | None:
    """Sidecar metadata for a cached URL (e.g. its Last-Modified), or None."""
    key = hashlib.sha256(full_url(url, params).encode()).hexdigest()[:20]
    p = _meta_path(key)
    return json.loads(p.read_text()) if p.exists() else None


def log_summary() -> str:
    """Markdown table of this run's requests, for pasting into REPORT.md."""
    lines = ["| kind | status | latency_ms | bytes | url |", "|---|---|---|---|---|"]
    for e in REQUEST_LOG:
        lines.append(f"| {e['kind']} | {e['status']} | {e['latency_ms']} | {e['bytes']} | {e['url'][:90]} |")
    return "\n".join(lines)
