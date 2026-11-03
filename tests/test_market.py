"""finn.market: price history and adjustment, key numbers, filing tags, signals, rerun detection."""
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from finn.data import corporate_actions as ca
from finn.data import eod
from finn.data.announcements import parse_announcements
from finn.market import filings, moves, prices, signals, stats
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


def test_results_quarters_carry_the_four_headline_figures(fx):
    df = tcs_frame(fx)
    q = stats.results_stats(df, None, close=3000.0)["quarters"][-1]
    last = df.iloc[-1]
    assert q["revenue_cr"] == pytest.approx(last["revenue"] / 1e7) and q["pat_cr"] == pytest.approx(last["pat"] / 1e7)
    assert q["pbt_cr"] == pytest.approx(last["pbt"] / 1e7)
    assert q["ebitda_cr"] == pytest.approx((last["pbt"] + last["finance_costs"] + last["dep_amort"]
                                            - last["other_income"]) / 1e7)
    assert q["approved"] and len(q["approved"]) == 10


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
def test_track_record_states():
    s = signals.track_record({"Kept": 4, "Missed": 1, "Dropped": 1})
    assert s["state"] == "enough" and s["facts"] == {"kept": 4, "missed": 1, "decided": 5, "dropped": 1}
    assert signals.track_record({"Kept": 1, "Missed": 1})["state"] == "few"
    assert signals.track_record(None)["state"] == "none"


@pytest.mark.parametrize("pos,state", [(0.1, "low"), (0.5, "middle"), (0.9, "high"), (None, "unknown")])
def test_price_trend_states(pos, state):
    p = {"return_1y": -8.2, "nifty_return_1y": 6.1, "range_position": pos, "close": 3412.5,
         "low_52w": 3300.0, "high_52w": 4280.0}
    assert signals.price_trend(p)["state"] == state
    assert signals.price_trend({"return_1y": None}) is None


@pytest.mark.parametrize("recent,usual,state", [(48, 41, "higher"), (30, 41, "lower"), (43, 41, "usual")])
def test_delivery_states(recent, usual, state):
    s = signals.delivery({"delivery_20d": recent, "delivery_avg": usual, "delivery_sessions": 63})
    assert s["state"] == state and s["facts"]["months"] == 3


def test_filings_flag():
    f = [{"worth_a_look": True, "tag": "Auditor change", "date": "2026-10-01", "pdf_url": "u"},
         {"worth_a_look": False, "tag": "Results", "date": "2026-10-02", "pdf_url": "v"}]
    s = signals.filings_flag(f, 90)
    assert s["state"] == "flagged" and s["facts"]["tags"] == ["Auditor change"] and len(s["items"]) == 1
    assert signals.filings_flag([], 90)["state"] == "clear"


def test_move_signal_comes_first():
    move = {"date": "2026-11-02", "change_pct": -12.0, "times": 6.0, "filings": []}
    out = signals.signals(None, None, [], 90, move)
    assert out[0]["key"] == "move" and out[0]["state"] == "down"


# --- big moves and alert events -------------------------------------------------------------
def calm_then(last_pct, n=120, volume_last=500):
    rows, close = [], 100.0
    for i in range(n):
        close *= 1.004 if i % 2 else 0.996                 # +-0.4% days
        rows.append(row(DAY - timedelta(days=n - i), close, volume=100))
    rows.append(row(DAY, close * (1 + last_pct / 100), volume=volume_last))
    return rows


def test_big_move_is_relative_to_the_stock():
    m = moves.big_move(calm_then(-3.0), [{"date": DAY.isoformat(), "tag": "Results", "pdf_url": "r"}])
    assert m and m["change_pct"] == pytest.approx(-3.0) and m["times"] > 5 and m["volume_x"] == pytest.approx(5.0)
    assert m["biggest_in_year"] and m["filings"][0]["tag"] == "Results"
    assert moves.big_move(calm_then(1.0)) is None            # 1%: neither 5% nor 2% and 3x typical
    assert moves.big_move(calm_then(-6.0))["change_pct"] < -5


def test_market_day():
    nifty = [{"date": DAY - timedelta(days=1), "close": 100.0}, {"date": DAY, "close": 97.5}]
    d = moves.market_day(nifty)
    assert d["big"] and d["change_pct"] == pytest.approx(-2.5)
    assert moves.market_day(nifty[:1]) is None


def test_events_are_only_what_changed():
    f_old = {"pdf_url": "a", "worth_a_look": True, "tag": "Resignation", "date": "2026-10-01"}
    f_new = {"pdf_url": "b", "worth_a_look": True, "tag": "Pledge", "date": "2026-11-02"}
    f_res = {"pdf_url": "c", "worth_a_look": False, "tag": "Results", "date": "2026-11-02"}
    f_plain = {"pdf_url": "d", "worth_a_look": False, "tag": "Press release", "date": "2026-11-02"}
    move = {"date": "2026-11-02", "change_pct": -7.0, "times": 4.0, "biggest_in_year": True}
    before = {"filings": [f_old], "move": None, "ledger_generated_at": "2026-10-01T00:00:00Z"}
    now = {"filings": [f_new, f_res, f_plain, f_old], "move": move, "ledger_generated_at": "2026-11-02T00:00:00Z",
           "ledger_counts": {"Kept": 5}}
    ev = moves.events("TCS", now, before)
    assert [e["kind"] for e in ev] == ["move", "flag", "results", "ledger"]
    assert moves.events("TCS", now, now | {"filings": now["filings"]}) == []     # same day, second run: nothing new
    assert moves.events("TCS", now, None) == []                                 # first run: nothing to compare


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


def test_evening_run_keeps_todays_prices_before_the_delivery_file(fx):
    px = eod.parse_udiff(fx("bhav_udiff_2026-10-30_sample.zip"))

    def eod_fn(d, delivery):
        if delivery:
            raise eod.NotYetPublished("delivery file comes at 23:55")
        return px.assign(date=d)

    rows, _ = prices.history(["TCS"], DAY, days=0, eod_fn=eod_fn, index_fn=lambda d: None)
    assert rows["TCS"][0]["date"] == DAY and rows["TCS"][0]["deliv_pct"] is None


def _results(qs, bank=False):
    return {"top_line": "total_income" if bank else "revenue", "basis": "Consolidated",
            "ebitda_note": "EBITDA is not meaningful for banks" if bank else None,
            "quarters": [{"quarter": f"Q{i}", "qe": qe, "approved": ap, "xbrl_url": "u",
                          "revenue_cr": rev, "ebitda_cr": None if bank else rev / 4, "pbt_cr": rev / 5, "pat_cr": pat}
                         for i, (qe, ap, rev, pat) in enumerate(qs)]}


QS = [("2025-09-30", "2025-10-20", 100.0, 10.0), ("2025-12-31", "2026-01-15", 105.0, -2.0),
      ("2026-03-31", "2026-04-20", 110.0, 12.0), ("2026-06-30", "2026-07-18", 115.0, 12.0),
      ("2026-09-30", "2026-10-17", 120.0, 15.0)]


def test_results_card_qoq_and_yoy():
    c = stats.results_card(_results(QS))
    rev, ebitda, pbt, pat = c["rows"]
    assert c["quarter"] == "Q4" and c["prev_quarter"] == "Q3" and c["year_quarter"] == "Q0"
    assert rev["key"] == "revenue" and rev["qoq"] == pytest.approx(120 / 115 * 100 - 100)
    assert rev["yoy"] == pytest.approx(20.0) and pat["yoy"] == pytest.approx(50.0)
    assert ebitda["now"] == pytest.approx(30.0) and "note" not in ebitda


def test_results_card_no_percent_on_a_loss_base_or_a_gap():
    c = stats.results_card(_results(QS), "2026-03-31")
    pat = c["rows"][3]
    assert pat["qoq"] is None                  # the quarter before was a loss
    assert c["year_quarter"] is None and pat["yoy"] is None
    gap = stats.results_card(_results([QS[0], QS[2]]))
    assert gap["prev_quarter"] is None and gap["rows"][0]["qoq"] is None


def test_results_card_bank_has_no_ebitda():
    c = stats.results_card(_results(QS, bank=True))
    assert c["rows"][0]["key"] == "total_income" and c["rows"][1]["now"] is None and c["rows"][1]["note"]


def test_card_for_filing_matches_the_board_meeting():
    r = _results(QS)
    assert stats.card_for_filing(r, "2026-10-17T16:05:00+05:30")["quarter"] == "Q4"
    assert stats.card_for_filing(r, "2026-10-19T09:00:00+05:30")["quarter"] == "Q4"
    assert stats.card_for_filing(r, "2026-11-30T09:00:00+05:30") is None
    assert stats.card_for_filing(r, None) is None
