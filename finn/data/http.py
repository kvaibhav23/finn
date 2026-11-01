"""Shared, polite HTTP for every NSE source: one session per site, throttle, cookies, cache.

Cache policies (chosen by the caller, per URL):
  "permanent" - files that never change (XBRL, PDFs, past bhavcopies, past announcement
                windows). Key = sha256(url)[:20], same scheme as spikes/, so data/raw is shared.
  "daily"     - "today" feeds and listings that grow (today's announcements, EQUITY_L,
                filing/report listings). Key = sha256(url + "@" + IST date)[:20].
  "none"      - always live.
A 404 is cached only when the caller says the URL is a past-dated permanent file
(cache_404=True): a holiday's bhavcopy never appears, but today's may just be late (trap 8).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import requests

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = Path(os.environ.get("FINN_CACHE_DIR", ROOT / "data" / "raw"))
NSE_HOME = "https://www.nseindia.com/"
TIMEOUT = 30

# Same headers as spikes 01-08 (no tuning to get past blocks).
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}
SITE_HEADERS = {"nse": {"Referer": NSE_HOME}, "plain": {}}
EXT_BY_TYPE = {"application/json": ".json", "text/html": ".html", "text/csv": ".csv",
               "application/pdf": ".pdf", "application/zip": ".zip",
               "application/xml": ".xml", "text/xml": ".xml"}


def today_ist() -> date:
    return datetime.now(IST).date()


class FetchError(RuntimeError):
    """A source returned something other than 200 (and the caller can't treat it as 'absent')."""


@dataclass
class Response:
    url: str
    status: int | None
    content: bytes | None
    content_type: str = ""
    latency_ms: int | None = None
    cached: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.content is not None

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self) -> "Response":
        if not self.ok:
            raise FetchError(f"{self.status} {self.error or ''} {self.url}")
        return self


class Client:
    MIN_INTERVAL = 1.1          # seconds between live requests, across all sites
    BACKOFF = (2.0, 4.0)        # re-warm + retry delays after a 401/403 from NSE

    def __init__(self, cache_dir: Path | str | None = None, today: date | None = None,
                 session_factory: Callable[[], requests.Session] = requests.Session,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._today = today
        self._session_factory = session_factory
        self._sleep, self._clock = sleep, clock
        self._sessions: dict[str, requests.Session] = {}
        self._warmed: set[str] = set()
        self._last_live: float | None = None
        self.log: list[dict] = []

    def today(self) -> date:
        return self._today or today_ist()

    # --- sessions, throttle, cookies -------------------------------------------------
    def session(self, site: str) -> requests.Session:
        if site not in self._sessions:
            s = self._session_factory()
            s.headers.update(BASE_HEADERS)
            s.headers.update(SITE_HEADERS[site])
            self._sessions[site] = s
        return self._sessions[site]

    def _throttle(self) -> None:
        if self._last_live is not None:
            wait = self.MIN_INTERVAL - (self._clock() - self._last_live)
            if wait > 0:
                self._sleep(wait)
        self._last_live = self._clock()

    def _warm(self, site: str) -> None:
        """Visit the NSE home page for cookies. It answers 403 even when the API then works."""
        self._throttle()
        try:
            r = self.session(site).get(NSE_HOME, timeout=TIMEOUT)
            self.log.append({"kind": "warm", "status": r.status_code, "url": NSE_HOME})
        except requests.RequestException as e:
            self.log.append({"kind": "warm", "status": None, "url": NSE_HOME, "error": type(e).__name__})
        self._warmed.add(site)

    def _live(self, site: str, url: str) -> Response:
        self._throttle()
        t0 = self._clock()
        try:
            r = self.session(site).get(url, timeout=TIMEOUT)
        except requests.RequestException as e:
            self.log.append({"kind": "live", "status": None, "url": url, "error": type(e).__name__})
            return Response(url, None, None, error=f"{type(e).__name__}: {e}")
        ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
        resp = Response(url, r.status_code, r.content, ctype, int((self._clock() - t0) * 1000))
        if r.status_code != 200:
            resp.error = f"HTTP {r.status_code}"
        self.log.append({"kind": "live", "status": r.status_code, "url": url})
        return resp

    # --- cache -----------------------------------------------------------------------
    def cache_key(self, url: str, policy: str) -> str | None:
        if policy == "permanent":
            return hashlib.sha256(url.encode()).hexdigest()[:20]
        if policy == "daily":
            return hashlib.sha256(f"{url}@{self.today().isoformat()}".encode()).hexdigest()[:20]
        if policy == "none":
            return None
        raise ValueError(f"unknown cache policy {policy!r}")

    def _read_cache(self, key: str, url: str) -> Response | None:
        meta_file = self.cache_dir / f"{key}.meta.json"
        if not meta_file.exists():
            return None
        meta = json.loads(meta_file.read_text())
        body = self.cache_dir / meta["file"]
        self.log.append({"kind": "cache", "status": meta["status"], "url": url})
        status = meta["status"]
        return Response(url, status, body.read_bytes(), meta.get("content_type", ""),
                        meta.get("latency_ms"), cached=True,
                        error=None if status == 200 else f"HTTP {status}")

    def _write_cache(self, key: str, resp: Response, last_modified: str | None = None) -> None:
        suffix = Path(resp.url.split("?")[0]).suffix.lower()
        ext = suffix if suffix in {".csv", ".zip", ".pdf", ".xml", ".json", ".txt"} \
            else EXT_BY_TYPE.get(resp.content_type, ".bin")
        body = self.cache_dir / f"{key}{ext}"
        body.write_bytes(resp.content or b"")
        (self.cache_dir / f"{key}.meta.json").write_text(json.dumps({
            "url": resp.url, "status": resp.status, "content_type": resp.content_type,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latency_ms": resp.latency_ms, "bytes": len(resp.content or b""), "file": body.name,
            "last_modified": last_modified}, indent=1))

    # --- public ----------------------------------------------------------------------
    def get(self, url: str, params: dict | None = None, *, site: str = "plain",
            policy: str = "permanent", cache_404: bool = False) -> Response:
        full = requests.Request("GET", url, params=params).prepare().url
        key = self.cache_key(full, policy)
        if key and (hit := self._read_cache(key, full)):
            return hit

        if site == "nse" and site not in self._warmed:
            self._warm(site)
        resp = self._live(site, full)
        if site == "nse" and resp.status in (401, 403):
            for delay in self.BACKOFF:
                self._sleep(delay)
                self._warm(site)
                resp = self._live(site, full)
                if resp.status not in (401, 403):
                    break

        if key and (resp.ok or (resp.status == 404 and cache_404 and policy == "permanent")):
            self._write_cache(key, resp)
        return resp


_default: Client | None = None


def client() -> Client:
    global _default
    if _default is None:
        _default = Client()
    return _default


def set_client(c: Client | None) -> None:
    """Swap the shared client (tests, or a different cache dir)."""
    global _default
    _default = c


def get(url: str, params: dict | None = None, **kw) -> Response:
    return client().get(url, params, **kw)


def window_policy(end: date, c: Client | None = None) -> str:
    """Windows that include today can still grow; fully past windows are immutable."""
    return "daily" if end >= (c or client()).today() else "permanent"
