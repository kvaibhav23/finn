"""financials: traps 1, 2, 4, 5 + receipts + derived metrics + market cap."""
import math
from datetime import date, datetime

import pandas as pd
import pytest

from finn.data import financials as fin
from finn.data.eod import UDIFF
from tests.conftest import FakeResponse

CR = 1e7  # INR per crore
TCS_Q = {date(2025, 12, 31): "xbrl_tcs_2025-12_cons.xml", date(2026, 3, 31): "xbrl_tcs_2026-03_cons.xml",
         date(2026, 6, 30): "xbrl_tcs_2026-06_cons.xml", date(2026, 9, 30): "xbrl_tcs_2026-09_cons.xml"}


def tcs_frame(fx, quarters=TCS_Q):
    rows = [fin.parse_xbrl(fx(f), qe, f) | {"symbol": "TCS"} for qe, f in quarters.items()]
    return fin.add_derived(pd.DataFrame(rows))


def test_trap1_legacy_ytd_context_rejected(fx):
    r = fin.parse_xbrl(fx("xbrl_tcs_2024-12_legacy.xml"), date(2024, 12, 31))
    assert r["revenue"] == 639_730_000_000          # quarter: 63,973 cr
    assert r["revenue"] != 1_908_450_000_000        # not the 9-month YTD (1,90,845 cr)


def test_trap2_bank_zero_ratios_become_missing(fx):
    for f, qe in [("xbrl_hdfcbank_2026-09_cons.xml", date(2026, 9, 30)),
                  ("xbrl_hdfcbank_2024-12_legacy.xml", date(2024, 12, 31))]:
        r = fin.parse_xbrl(fx(f), qe)
        assert math.isnan(r["gross_npa_pct"]) and math.isnan(r["cet1_ratio"])
        assert any("gross_npa_pct" in n for n in r["notes"])


def test_trap4_banking_taxonomy(fx):
    r = fin.parse_xbrl(fx("xbrl_hdfcbank_2026-09_cons.xml"), date(2026, 9, 30))
    assert r["taxonomy"] == "banking"
    assert r["interest_earned"] == 951_316_300_000 and math.isnan(r["revenue"])
    assert r["pat"] == 207_000_300_000 and r["receipts"]["pat"]["tag"] == "ProfitLossForThePeriod"


def test_trap5_listings_merge_across_the_2025_switch(fx):
    m = fin.merge_listings(fin.parse_integrated_listing(fx("listing_tcs_integrated.json")),
                           fin.parse_legacy_listing(fx("listing_tcs_legacy.json")))
    cons = sorted(set(m.loc[m["basis"] == "Consolidated", "qe"]))
    assert date(2024, 12, 31) in cons and date(2025, 3, 31) in cons
    p = [pd.Period(q, freq="Q") for q in cons if q >= date(2023, 3, 31)]
    assert all((b - a).n == 1 for a, b in zip(p, p[1:]))      # no gap at the legacy -> integrated switch
    picked = fin.pick_quarters(m, 8)
    assert set(picked["source"]) == {"legacy", "integrated"}


def test_every_value_has_a_receipt(fx):
    url = "https://nsearchives.nseindia.com/corporate/xbrl/X.xml"
    r = fin.parse_xbrl(fx("xbrl_tcs_2026-09_cons.xml"), date(2026, 9, 30), url)
    assert r["receipts"]["revenue"] == {"tag": "RevenueFromOperations", "xbrl_url": url}
    for field, v in r.items():
        if field in fin.VALUE_FIELDS and not (isinstance(v, float) and math.isnan(v)):
            assert field in r["receipts"]


def test_derived_ebitda_margins_shares(fx):
    q2 = tcs_frame(fx).iloc[-1]
    assert q2["ebitda"] == pytest.approx((18638 + 252 + 1262 - 1337) * CR)   # pbt + fin + d&a - other income
    assert q2["receipts"]["ebitda"]["derived"] is True
    assert q2["receipts"]["ebitda"]["formula"] == "pbt + finance_costs + dep_amort - other_income"
    assert q2["ebitda_margin"] == pytest.approx(q2["ebitda"] / (73188 * CR))
    assert q2["pat_margin"] == pytest.approx(13934 / 73188, rel=1e-3)
    assert q2["shares_outstanding"] == 3_620_000_000


def test_ttm_needs_four_consecutive_quarters(fx):
    df = tcs_frame(fx)
    assert df["ttm_revenue"].iloc[-1] == pytest.approx((67087 + 70698 + 72275 + 73188) * CR)
    assert df["ttm_revenue"].iloc[:3].isna().all()
    gap = {q: f for q, f in TCS_Q.items() if q != date(2026, 3, 31)}
    gap[date(2024, 12, 31)] = "xbrl_tcs_2024-12_legacy.xml"
    assert tcs_frame(fx, gap)["ttm_revenue"].isna().all()   # Mar-25..Sep-25 missing -> no TTM


def test_bank_derived_metrics_labelled(fx):
    r = fin.parse_xbrl(fx("xbrl_hdfcbank_2026-09_cons.xml"), date(2026, 9, 30))
    d = fin.add_derived(pd.DataFrame([r])).iloc[0]
    assert math.isnan(d["ebitda"]) and "not meaningful" in d["receipts"]["ebitda"]["note"]
    assert d["receipts"]["pat_margin"]["formula"] == "pat / total_income"


def test_market_cap_from_quarter_end_close(fx):
    df = tcs_frame(fx)
    out = fin.add_market_cap(df, "TCS", lambda sym, qe: (2502.6, date(2026, 10, 30), "udiff-url"))
    assert out["market_cap"].iloc[-1] == pytest.approx(3_620_000_000 * 2502.6)
    assert out["receipts"].iloc[-1]["market_cap"]["formula"] == "shares_outstanding x close_at_qe"


def test_nearest_close_walks_back_over_non_trading_days(fake_client, fx):
    c = fake_client({UDIFF.format(d=date(2026, 10, 30)): [FakeResponse(200, fx("bhav_udiff_2026-10-30_sample.zip"))]},
                    today=date(2026, 11, 2))
    close, day, src = fin.nearest_close("TCS", date(2026, 11, 1), client=c)   # Sun -> Sat (404) -> Fri
    assert (close, day) == (2502.6, date(2026, 10, 30)) and src.endswith("20261030_F_0000.csv.zip")
