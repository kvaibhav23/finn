from datetime import date

import pytest

from finn.data.http import NSE_HOME, Client
from tests.conftest import FakeResponse

URL = "https://www.nseindia.com/api/x"
FILE = "https://nsearchives.nseindia.com/corporate/a.pdf"


def test_network_is_blocked_in_tests(tmp_path):
    with pytest.raises(AssertionError, match="network"):
        Client(cache_dir=tmp_path).get("https://example.com/", policy="none")


def test_throttle_spaces_live_requests(fake_client):
    c = fake_client({"*": [FakeResponse(200, b"x")]})
    for i in range(3):
        c.get(f"https://nsearchives.nseindia.com/f{i}", policy="none")
    assert c.fake_clock.sleeps and all(s >= 1.1 - 1e-9 for s in c.fake_clock.sleeps)
    assert len(c.fake_session.calls) == 3


def test_nse_warms_up_once_then_requests(fake_client):
    c = fake_client({NSE_HOME: [FakeResponse(403, b"denied")], URL: [FakeResponse(200, b"[]")]})
    assert c.get(URL, site="nse", policy="none").ok
    c.get(URL, site="nse", policy="none")
    assert c.fake_session.calls.count(NSE_HOME) == 1  # the home page's own 403 is ignored


def test_rewarm_with_backoff_on_403(fake_client):
    c = fake_client({NSE_HOME: [FakeResponse(403)], URL: [FakeResponse(403), FakeResponse(200, b"[1]")]})
    r = c.get(URL, site="nse", policy="none")
    assert r.ok and r.content == b"[1]"
    assert c.fake_session.calls == [NSE_HOME, URL, NSE_HOME, URL]
    assert 2.0 in c.fake_clock.sleeps  # first backoff step


def test_gives_up_after_backoff_and_returns_failure(fake_client):
    c = fake_client({NSE_HOME: [FakeResponse(403)], URL: [FakeResponse(401)]})
    r = c.get(URL, site="nse", policy="none")
    assert r.status == 401 and not r.ok
    assert c.fake_session.calls.count(URL) == 3  # first try + 2 backoff retries
    assert {2.0, 4.0} <= set(c.fake_clock.sleeps)


def test_permanent_cache_never_refetches(fake_client):
    c = fake_client({FILE: [FakeResponse(200, b"%PDF-1", "application/pdf")]})
    assert c.get(FILE).content == b"%PDF-1"
    again = c.get(FILE)
    assert again.cached and len(c.fake_session.calls) == 1


def test_daily_cache_key_changes_with_the_day(fake_client, tmp_path):
    c1 = fake_client({URL: [FakeResponse(200, b"day1")]}, today=date(2026, 11, 2))
    assert c1.get(URL, policy="daily").content == b"day1"
    assert c1.get(URL, policy="daily").cached
    c2 = fake_client({URL: [FakeResponse(200, b"day2")]}, today=date(2026, 11, 3))
    assert c2.get(URL, policy="daily").content == b"day2"  # new day -> new key -> live
    assert c1.cache_key(URL, "daily") != c2.cache_key(URL, "daily")


def test_permanent_key_matches_spike_cache_scheme(tmp_path):
    import hashlib
    assert Client(cache_dir=tmp_path).cache_key(FILE, "permanent") == hashlib.sha256(FILE.encode()).hexdigest()[:20]


def test_404_cached_only_when_allowed(fake_client):
    c = fake_client({FILE: [FakeResponse(404)]})
    c.get(FILE, cache_404=False)
    c.get(FILE, cache_404=False)
    assert len(c.fake_session.calls) == 2           # not cached
    c.get(FILE, cache_404=True)
    hit = c.get(FILE, cache_404=True)
    assert hit.cached and hit.status == 404 and not hit.ok
