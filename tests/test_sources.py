"""symbols, announcements (trap 6), eod (trap 8)."""
from datetime import date

import pytest

from finn.data import announcements as an
from finn.data import eod
from finn.data.symbols import parse_equity_list, resolve_symbol
from tests.conftest import FakeResponse

DAY = date(2026, 10, 30)


def test_resolve_symbol(fx):
    master = parse_equity_list(fx("equity_l_sample.csv"))
    assert resolve_symbol("tcs", master)["isin"] == "INE467B01029"
    with pytest.raises(KeyError):
        resolve_symbol("NOTATICKER", master)


def test_trap6_hasxbrl_dropped_and_seq_id_dedupe(fx):
    df = an.parse_announcements(fx("ann_reliance_2026-10.json"))
    assert len(df) == 18 and "hasXbrl" not in df.columns
    assert df["seq_id"].is_unique
    # Same symbol + same second, two different filings: both kept (dedupe is on seq_id only).
    same = df[(df["category"] == "Outcome of Board Meeting") & (df["filed_at"] == "2026-10-30 19:40:11")]
    assert len(same) == 2 and same["pdf_url"].nunique() == 2
    # Overlapping windows (the same rows fetched twice) collapse back to 18.
    assert len(an.combine([df, an.parse_announcements(fx("ann_reliance_2026-10.json"))])) == 18


def test_get_announcements_market_wide_per_day(fake_client, fx):
    c = fake_client({"*": [FakeResponse(200, fx("ann_reliance_2026-10.json"), "application/json")]},
                    today=date(2026, 11, 2))
    df = an.get_announcements(date(2026, 10, 30), date(2026, 10, 31), client=c)
    api_calls = [u for u in c.fake_session.calls if "/api/" in u]
    assert len(api_calls) == 2 and len(df) == 18  # one request per day, deduped


def test_parse_udiff_and_delivery(fx):
    px = eod.parse_udiff(fx("bhav_udiff_2026-10-30_sample.zip"))
    tcs = px[(px["symbol"] == "TCS") & (px["series"] == "EQ")].iloc[0]
    assert (tcs["close"], tcs["prev_close"], tcs["volume"]) == (2502.6, 2478.0, 3016983)
    full = eod.parse_full(fx("bhav_full_2026-10-30_sample.csv"))
    assert full.set_index(["symbol", "series"]).loc[("TCS", "EQ"), "deliv_pct"] == 47.09


def test_get_eod_trading_day(fake_client, fx):
    c = fake_client({eod.UDIFF.format(d=DAY): [FakeResponse(200, fx("bhav_udiff_2026-10-30_sample.zip"))]},
                    today=date(2026, 11, 2))
    df = eod.get_eod(DAY, client=c)
    assert df.loc[df["symbol"] == "DIXON", "close"].iloc[0] == 11000.0


def test_trap8_past_404_is_holiday_and_cached(fake_client):
    sat = date(2026, 10, 31)
    c = fake_client({}, today=date(2026, 11, 2))
    assert eod.get_eod(sat, client=c) is None
    assert eod.get_eod(sat, client=c) is None
    assert len(c.fake_session.calls) == 1  # second answer came from cache


def test_trap8_today_404_is_not_yet_published_and_not_cached(fake_client):
    today = date(2026, 11, 2)
    c = fake_client({}, today=today)
    for _ in range(2):
        with pytest.raises(eod.NotYetPublished):
            eod.get_eod(today, client=c)
    assert len(c.fake_session.calls) == 2  # retried live, never cached
