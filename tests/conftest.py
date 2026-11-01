"""Tests run fully offline: any real HTTP request fails the test."""
from __future__ import annotations

from pathlib import Path

import pytest
import requests

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*a, **k):
        raise AssertionError("network access attempted in tests")
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", blocked)


@pytest.fixture
def fx():
    """Read a fixture file as bytes."""
    return lambda name: (FIXTURES / name).read_bytes()


class FakeResponse:
    def __init__(self, status: int, content: bytes = b"", ctype: str = "application/octet-stream"):
        self.status_code, self.content = status, content
        self.headers = {"Content-Type": ctype}


class FakeSession:
    """Stands in for requests.Session. `routes` maps URL -> list of responses (served in order)."""
    def __init__(self, routes: dict):
        self.routes = {k: list(v) for k, v in routes.items()}
        self.headers, self.calls = {}, []

    def get(self, url, timeout=None):
        self.calls.append(url)
        queue = self.routes.get(url) or self.routes.get("*")
        if not queue:
            return FakeResponse(404, b"not found", "text/html")
        return queue.pop(0) if len(queue) > 1 else queue[0]


class FakeClock:
    def __init__(self):
        self.t, self.sleeps = 1000.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


@pytest.fixture
def fake_client(tmp_path):
    """Build an http.Client wired to a FakeSession + fake clock, caching into tmp_path."""
    from finn.data.http import Client

    def make(routes: dict, today=None):
        session, clock = FakeSession(routes), FakeClock()
        c = Client(cache_dir=tmp_path, today=today, session_factory=lambda: session,
                   sleep=clock.sleep, clock=clock)
        c.fake_session, c.fake_clock = session, clock
        return c
    return make
