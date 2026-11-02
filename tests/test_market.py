"""finn.market: price history and adjustment, key numbers, filing tags, signals, rerun detection."""
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from finn.data import corporate_actions as ca
from finn.data import eod
from finn.data.announcements import parse_announcements
from finn.market import filings, prices, signals, stats
from finn.market.__main__ import needs_rerun
from tests.test_financials import tcs_frame

DAY = date(2026, 10, 30)


def row(d, close, high=None, low=None, volume=100, deliv=None):
    return {"date": d, "open": close, "high": high or close, "low": low or close, "close": close,
            "volume": volume, "deliv_pct": deliv}


# --- prices -------------------------------------------------------------------------------
def test_history_reads_each_market_file_once_and_skips_holidays(fx):
    px = eod.parse_udiff(fx("bhav_udiff_2026-10-30_sample.zip"))
    full = eod.parse_full(fx("bhav_full_2026-10-30_sample.csv"))
    seen = []

    def eod_fn(d, delivery):
        seen.append((d, delivery))
        if d == date(2026, 10, 29):
            return None                                   # holiday
        if d == DAY:
            raise eod.NotYetPublished("late")            # today's file not out yet
        df = px.assign(date=d)
        return df.merge(full, on=["symbol", "series"], how="left") if delivery else df

    rows, nifty = prices.history(["TCS", "DIXON"], DAY, days=6, delivery_days=2, eod_fn=eod_fn,
                                 index_fn=lambda d: {"Nifty 50": 23000.0})
    assert [r["date"] for r in rows["TCS"]] == [date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28)]
    assert rows["TCS"][-1]["deliv_pct"] is not None and rows["TCS"][0]["deliv_pct"] is None
    assert all(d.weekday() < 5 for d, _ in seen)
    assert [n["date"] for n in nifty] == [r["date"] for r in rows["TCS"]]


def test_delivery_file_missing_falls_back_to_prices(fx):
    px = eod.parse_udiff(fx("bhav_udiff_2026-10-30_sample.zip"))

    def eod_fn(d, delivery):
        if delivery:
            raise eod.http.FetchError("delivery file missing")
        return px.assign(date=d)

    rows, _ = prices.history(["TCS"], DAY, days=0, eod_fn=eod_fn, index_fn=lambda d: None)
    assert rows["TCS"][0]["close"] > 0 and rows["TCS"][0]["deliv_pct"] is None


def test_split_and_bonus_adjust_past_prices():
    acts = pd.DataFrame([{"subject": "Bonus 1:1", "type": "bonus", "ex_date": date(2026, 10, 28),
                          "factor": 2.0}])
    rows = [row(date(2026, 10, 27), 200.0, volume=10), row(date(2026, 10, 28), 101.0, volume=30)]
    out, applied = prices.adjust(rows, acts)
    assert [r["close"] for r in out] == [100.0, 101.0] and out[0]["volume"] == 20
    assert applied == ["Bonus 1:1"]
    assert prices.adjust(rows, None) == (rows, [])


# --- key numbers --------------------------------------------------------------------------
def year_of_rows(start_close=100.0, end_close=120.0, deliv=None):
    days = [DAY - timedelta(days=i) for i in range(380, -1, -1) if (DAY - timedelta(days=i)).weekday() < 5]
    step = (end_close - start_close) / (len(days) - 1)
    return [row(d, start_close + i * step, deliv=deliv(i) if deliv else None) for i, d in enumerate(days)]


def test_price_stats():
    rows = year_of_rows(deliv=lambda i: 50.0 if i > 250 else 40.0)
    nifty = [{"date": r["date"], "close": 1000 + i} for i, r in enumerate(rows)]
    p = stats.price_stats(rows, nifty)
    assert p["close"] == pytest.approx(120.0) and p["as_of"] == "2026-10-30"
    assert p["change"] > 0 and p["range_position"] == pytest.approx(1.0)
    assert 0 < p["return_1y"] < 20 and p["nifty_return_1y"] > 0
    assert p["delivery_20d"] == 50.0 and 40 < p["delivery_avg"] < 50


def test_price_stats_needs_a_year_for_returns():
    p = stats.price_stats([row(DAY - timedelta(days=1), 10.0), row(DAY, 11.0)], [])
    assert p["return_1y"] is None and p["nifty_return_1y"] is None and p["change_pct"] == pytest.approx(10.0)
    assert stats.price_stats([], []) is None


def test_results_stats_tcs(fx):
    df = tcs_frame(fx)
    r = stats.results_stats(df, None, close=3000.0)
    eps = df["eps_diluted"].sum()
    assert r["pe"] == pytest.approx(3000.0 / eps)
    assert r["market_cap_cr"] == pytest.approx(df["shares_outstanding"].iloc[-1] * 3000 / 1e7)
    assert r["ttm_revenue_cr"] == pytest.approx(df["revenue"].sum() / 1e7)
    assert r["latest_quarter"] == "Q2FY27" and len(r["quarters"]) == 4
    assert r["revenue_yoy_pct"] is None                  # no quarter a year earlier in the frame


def test_pe_after_a_bonus_uses_adjusted_eps(fx):
    df = tcs_frame(fx)
    acts = pd.DataFrame([{"subject": "Bonus 1:1", "type": "bonus", "ex_date": date(2026, 12, 1), "factor": 2.0}])
    plain, adj = stats.results_stats(df, None, 3000.0), stats.results_stats(df, acts, 1500.0)
    assert adj["pe"] == pytest.approx(plain["pe"])                       # same company, half the price
    assert adj["market_cap_cr"] == pytest.approx(plain["market_cap_cr"])  # twice the shares


def test_pe_loss_making(fx):
    df = tcs_frame(fx)
    df["eps_diluted"] = -1.0
    r = stats.results_stats(df, None, 3000.0)
    assert r["pe"] is None and "loss" in r["pe_note"]


# --- filings ------------------------------------------------------------------------------
@pytest.mark.parametrize("category,subject,expected", [
    ("Change in Auditors", "Resignation of statutory auditor", "Auditor change"),
    ("General Updates", "Creation of pledge on promoter shares", "Pledge"),
    ("Action(s) taken or orders passed", "Order from GST department", "Regulatory or legal"),
    ("Change in Director(s)", "Cessation of Mr X as director", "Resignation"),
    ("Appointment", "Appointment of CFO", "Appointment"),
    ("Credit Rating", "ICRA reaffirmed AAA", "Credit rating"),
    ("Outcome of Board Meeting", "approved the financial results for the quarter", "Results"),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Transcript of the call", "Earnings call"),
    ("Dividend", "Interim dividend of Rs 5", "Dividend or corporate action"),
    ("Copy of Newspaper Publication", "Results published in newspapers", None),
    ("Trading Window", "Closure of trading window", None),
    ("General Updates", "Something else entirely", "Other"),
])
def test_filing_tags(category, subject, expected):
    assert filings.tag(category, subject) == expected


def test_recent_filings_drop_paperwork_and_link_pdfs(fx):
    ann = parse_announcements(fx("ann_asianpaint_13m.json"))
    out = filings.recent(ann, limit=200)
    assert out and all(f["pdf_url"].startswith("https://") for f in out)
    assert not any("Newspaper" in f["category"] for f in out)
    assert [f["date"] for f in out] == sorted([f["date"] for f in out], reverse=True)
    assert any(f["worth_a_look"] for f in out)           # the fixture has a change of auditors


# --- signals ------------------------------------------------------------------------------
def test_track_record_wording():
    s = signals.track_record({"Kept": 4, "Missed": 1, "Dropped": 1})
    assert s["text"] == "Kept 4 of the 5 promises whose results are in."
    assert s["detail"] == "1 more was never mentioned again."
    assert "too few" in signals.track_record({"Kept": 1, "Missed": 1})["text"]
    assert "hasn't checked" in signals.track_record(None)["text"]


def test_price_trend_wording():
    p = {"return_1y": -8.24, "nifty_return_1y": 6.1, "range_position": 0.1, "close": 3412.5,
         "low_52w": 3300.0, "high_52w": 4280.0}
    s = signals.price_trend(p)
    assert s["text"] == "Down 8.2% in a year; the Nifty 50 rose 6.1% over the same days."
    assert "near its 52-week low" in s["detail"] and "₹3,300.00" in s["detail"]
    assert signals.price_trend({"return_1y": None}) is None


@pytest.mark.parametrize("recent,usual,word", [(48, 41, "Higher"), (30, 41, "Lower"), (43, 41, "About usual")])
def test_delivery_wording(recent, usual, word):
    s = signals.delivery({"delivery_20d": recent, "delivery_avg": usual, "delivery_sessions": 63})
    assert s["detail"].startswith(word) and "last 3 months" in s["text"]


def test_filings_flag():
    f = [{"worth_a_look": True, "tag": "Auditor change", "date": "2026-10-01", "pdf_url": "u"},
         {"worth_a_look": False, "tag": "Results", "date": "2026-10-02", "pdf_url": "v"}]
    s = signals.filings_flag(f, 90)
    assert s["text"] == "1 filing worth a look in the last 90 days: auditor change." and len(s["items"]) == 1
    assert signals.filings_flag([], 90)["text"].startswith("No resignations")


# --- rerun detection ----------------------------------------------------------------------
def test_needs_rerun_on_new_transcript_or_results():
    L = {"status": "ok", "calls": [{"quarter_end": "2026-06-30"}], "as_of_results": "2026-06-30"}
    ann = pd.DataFrame([{"category": "Analysts/Institutional Investor Meet/Con. Call Updates",
                         "subject": "Transcript of the earnings conference call",
                         "filed_at": datetime(2026, 10, 20, 18, 0)}])
    assert "2026-09-30" in needs_rerun(L, ann, None)
    assert "results" in needs_rerun(L, ann.iloc[0:0], "2026-09-30")
    assert needs_rerun(L, ann.iloc[0:0], "2026-06-30") is None
    assert needs_rerun({"status": "failed"}, ann, None) is None


def test_call_dates_from_transcript_filings(fx):
    ann = parse_announcements(fx("ann_asianpaint_13m.json"))
    calls = filings.call_dates(ann)
    assert calls and [c["date"] for c in calls] == sorted(c["date"] for c in calls)
    assert len({c["quarter"] for c in calls}) == len(calls)
    assert all(c["quarter"].startswith("Q") and c["pdf_url"] for c in calls)


def test_within_keeps_recent_filings(fx):
    ann = parse_announcements(fx("ann_asianpaint_13m.json"))
    end = ann["filed_at"].max().date()
    w = filings.within(ann, end, 30)
    assert 0 < len(w) < len(ann) and (w["filed_at"].dt.date > end - timedelta(days=30)).all()


def test_call_date_is_the_recording_not_the_transcript():
    cat = "Analysts/Institutional Investor Meet/Con. Call Updates"
    ann = pd.DataFrame([
        {"category": cat, "subject": "Link of Recording", "filed_at": datetime(2026, 7, 29, 19), "pdf_url": "r1"},
        {"category": cat, "subject": "Transcript of the investor conference", "filed_at": datetime(2026, 8, 3, 12),
         "pdf_url": "t1"},
        {"category": "General Updates", "subject": "80th AGM Transcript and video", "filed_at": datetime(2026, 7, 16),
         "pdf_url": "agm"},
        {"category": cat, "subject": "Link of Recording", "filed_at": datetime(2026, 10, 29, 19), "pdf_url": "r2"},
    ])
    assert filings.call_dates(ann) == [{"quarter": "Q1FY27", "date": "2026-07-29", "pdf_url": "t1"},
                                       {"quarter": "Q2FY27", "date": "2026-10-29", "pdf_url": "r2"}]
