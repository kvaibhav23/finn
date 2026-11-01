"""corporate actions + trap 3 (EPS break across HDFCBANK's 1:1 bonus)."""
from datetime import date

import pandas as pd
import pytest

from finn.data import corporate_actions as ca
from finn.data import financials as fin


@pytest.mark.parametrize("subject,kind,factor", [
    ("Bonus 1:1", "bonus", 2.0),
    ("Bonus 3:2", "bonus", 2.5),
    ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share", "split", 5.0),
    ("Face Value Split From Rs.10/- To Rs.2/-", "split", 5.0),
    ("Rights 1:15 @ Premium Rs 1247", "rights", 1.0),
    ("Dividend - Rs 13 Per Share", "dividend", 1.0),
])
def test_classify(subject, kind, factor):
    k, f, _ = ca.classify(subject)
    assert (k, f) == (kind, factor)


def test_parse_hdfcbank_actions(fx):
    acts = ca.parse_corporate_actions(fx("ca_hdfcbank.json"))
    bonus = acts[acts["type"] == "bonus"].iloc[0]
    assert (bonus["ex_date"], bonus["factor"]) == (date(2025, 8, 26), 2.0)


def test_trap3_eps_adjusted_for_bonus(fx):
    acts = ca.parse_corporate_actions(fx("ca_hdfcbank.json"))
    rows = [fin.parse_xbrl(fx("xbrl_hdfcbank_2024-12_legacy.xml"), date(2024, 12, 31)),
            fin.parse_xbrl(fx("xbrl_hdfcbank_2026-09_cons.xml"), date(2026, 9, 30))]
    df = ca.adjust_per_share(fin.add_derived(pd.DataFrame(rows)), acts)
    dec24, sep26 = df.iloc[0], df.iloc[1]
    assert dec24["eps_basic"] == 23.11 and dec24["adj_factor"] == 2.0     # published Jan-2025, before the bonus
    assert dec24["eps_basic_adj"] == pytest.approx(11.555)
    assert sep26["adj_factor"] == 1.0 and sep26["eps_basic_adj"] == 13.43  # published after: already restated
    assert dec24["receipts"]["eps_basic_adj"]["actions"] == ["Bonus 1:1"]
    # Cross-check against XBRL share capital: shares roughly doubled across the bonus.
    ratio = sep26["shares_outstanding"] / dec24["shares_outstanding"]
    assert ratio == pytest.approx(dec24["adj_factor"], rel=0.02)


def test_adjustment_keys_on_publication_not_quarter_end():
    acts = pd.DataFrame([{"subject": "Bonus 1:1", "type": "bonus", "ex_date": date(2025, 8, 26), "factor": 2.0}])
    df = pd.DataFrame([{"eps_basic": 10.0, "board_meeting": "2025-07-20", "receipts": {}},   # Jun-25 qtr, before
                       {"eps_basic": 5.0, "board_meeting": "2025-10-15", "receipts": {}}])  # Sep-25 qtr, restated
    out = ca.adjust_per_share(df, acts, cols=("eps_basic",))
    assert list(out["eps_basic_adj"]) == [5.0, 5.0]
