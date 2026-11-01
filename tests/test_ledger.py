"""finn/ledger: periods, classify guards, threading, resolution (XBRL + calibration), verdict rules, eval."""
import json
from datetime import date

import pandas as pd
import pytest

from finn.data import financials as fin
from finn.ledger import classify as cl
from finn.ledger import eval as ev
from finn.ledger import resolve as rs
from finn.ledger import thread as th
from finn.ledger import verdict as vd
from finn.ledger.periods import fy_label, resolve_horizon

FY26 = [date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31), date(2026, 3, 31)]


def target(kind="range", low=18.0, high=20.0, unit="pct", comparator="range"):
    return {"kind": kind, "low_text": "" if low is None else f"{low:g}", "high_text": "" if high is None else f"{high:g}",
            "unit": unit, "comparator": comparator, "low": low, "high": high}


def commit(cid, quarter, qe, metric="pbdit_margin", tgt=None, end=date(2026, 3, 31), scope="company",
           basis="unspecified", subject="", quote=None):
    h = None if end is None else {"end": end, "quarters": FY26 if end == date(2026, 3, 31) else [end], "assumed": False,
                                  "token": "FY26"}
    return {"id": cid, "quarter": quarter, "quarter_end": qe, "page": 3, "speaker": "CEO", "metric": metric,
            "target": tgt or target(), "horizon": h, "conditional": False, "scope": scope, "basis": basis,
            "subject": subject, "quote": quote or f"quote {cid}", "sentence": quote or f"quote {cid}"}


# --- periods ---------------------------------------------------------------------------------
@pytest.mark.parametrize("token,call_qe,end,n", [
    ("FY27", date(2026, 6, 30), date(2027, 3, 31), 4),
    ("Q3FY27", date(2026, 6, 30), date(2026, 12, 31), 1),
    ("H2FY27", date(2026, 6, 30), date(2027, 3, 31), 2),
    ("next_quarter", date(2026, 6, 30), date(2026, 12, 31), 1),     # call held in Q2 -> next is Q3
    ("current_quarter", date(2026, 6, 30), date(2026, 9, 30), 1),
    ("none", date(2026, 3, 31), date(2027, 3, 31), 4),             # Q4 call is held in the next FY
])
def test_resolve_horizon(token, call_qe, end, n):
    h = resolve_horizon(token, call_qe)
    assert h["end"] == end and len(h["quarters"]) == n and h["assumed"] == (token == "none")


def test_open_ended_horizon_and_fy_label():
    assert resolve_horizon("medium_term", date(2026, 6, 30)) is None
    assert fy_label(date(2026, 3, 31)) == "Q4FY26" and fy_label(date(2026, 6, 30)) == "Q1FY27"


# --- classify guards -------------------------------------------------------------------------
def test_classify_guards(fake_llm):
    text = "We will keep the guidance of 18 to 20% PBDIT margin. Capex will be Rs 700 crores. Thank you."
    cands = [{"id": f"X-Q1FY27-00{i}", "speaker": "CEO", "page": 2, "context": "", "sentence": s}
             for i, s in enumerate(["We will keep the guidance of 18 to 20% PBDIT margin.", "Capex will be Rs 700 crores.",
                                    "We will keep growing.", "Thank you.", "Something else."], 1)]
    item = lambda i, quote, lo, hi: {"id": f"X-Q1FY27-00{i}", "metric": "pbdit_margin", "target": {
        "kind": "range", "low_text": lo, "high_text": hi, "unit": "pct", "comparator": "range"},
        "horizon_token": "FY27", "conditional": False, "scope": "company", "basis": "unspecified", "subject": "",
        "quote": quote}
    fake_llm([json.dumps({"non_commitment_ids": ["X-Q1FY27-004"], "commitments": [
        item(1, "guidance of 18 to 20% PBDIT margin", "18", "20"),          # passes
        item(2, "Capex will be Rs 700 crores.", "750", ""),                  # 750 is not in the quote
        item(3, "We will keep growing strongly.", "", "")]})])               # not verbatim (and no number)
    call = {"symbol": "X", "quarter": "Q1FY27", "quarter_end": date(2026, 6, 30), "text": text, "candidates": cands}
    rows, rejected = cl.classify_call(call)
    by = {r["id"]: r for r in rows}
    assert by["X-Q1FY27-001"]["is_commitment"] and by["X-Q1FY27-001"]["target"]["low"] == 18.0
    assert by["X-Q1FY27-001"]["horizon"]["end"] == date(2027, 3, 31)
    reasons = {r["id"]: r["reason"] for r in rejected}
    assert "not in quote" in reasons["X-Q1FY27-002"] and "verbatim" in reasons["X-Q1FY27-003"]
    assert by["X-Q1FY27-004"]["is_commitment"] is False
    assert reasons["X-Q1FY27-005"] == "model returned no label for this id" and by["X-Q1FY27-005"]["is_commitment"] is None


def test_numbers_compare_by_value():
    assert cl.numbers("INR1,100 crores, 9.0% and 18.5.") == ["1100", "9", "18.5"]


# --- threading -------------------------------------------------------------------------------
def test_thread_reaffirm_revise_and_numberless_reference():
    q = [("Q1FY26", date(2025, 6, 30)), ("Q2FY26", date(2025, 9, 30)), ("Q3FY26", date(2025, 12, 31))]
    calls = [[commit("A", *q[0], basis="standalone")],
             [commit("B", *q[1], tgt=target("none", None, None, "none", "none"))],   # "we'll maintain our guidance"
             [commit("C", *q[2], tgt=target(low=19.0, high=21.0))]]
    t = th.thread(calls, "X")
    assert len(t) == 1
    assert [v["status"] for v in t[0]["versions"]] == ["New", "Reaffirmed", "Revised"]
    assert t[0]["versions"][2]["revised_from"]["target"]["low"] == 18.0
    assert th.effective(t[0])["id"] == "C"


def test_segment_targets_are_not_linked_by_metric(fake_llm):
    fake_llm([json.dumps({"links": [{"new_id": "B", "match_id": "Z-invented"}]})])   # invented id is ignored
    calls = [[commit("A", "Q1FY26", date(2025, 6, 30), scope="segment", subject="mobile margin")],
             [commit("B", "Q2FY26", date(2025, 9, 30), scope="segment", subject="TV margin")]]
    assert len(th.thread(calls, "X")) == 2


def test_inr_targets_far_apart_are_not_one_thread():
    cr = lambda lo, hi: target("range", lo, hi, "inr_cr")
    calls = [[commit("A", "Q1FY26", date(2025, 6, 30), metric="capex", tgt=cr(900.0, 1000.0))],
             [commit("B", "Q2FY26", date(2025, 9, 30), metric="capex", tgt=cr(150.0, 150.0))],
             [commit("C", "Q3FY26", date(2025, 12, 31), metric="capex", tgt=cr(1100.0, 1200.0))]]
    t = th.thread(calls, "X")
    assert [[v["id"] for v in x["versions"]] for x in t] == [["A", "C"], ["B"]]


def test_implausible_self_reported_figure_and_direction_events_are_ignored():
    vol = th.thread([[commit("A", "Q1FY26", date(2025, 6, 30), metric="volume_growth", scope="segment",
                             tgt=target("value", 0.5, None, "units", "about"), end=date(2026, 3, 31))]], "X")[0]
    fact = {"kind": "value", "value": 33.0, "period_end": date(2026, 3, 31), "quarter": "Q4FY26", "page": 16}
    assert rs.resolve(vol, [fact], synthetic_fin(FY26), date(2026, 3, 31))["source"] == "unverifiable"
    trend = th.thread([[commit("D", "Q1FY26", date(2025, 6, 30), metric="direction",
                               tgt=target("direction", None, None, "none", "up"))]], "X")[0]
    done = {"kind": "event_done", "value": None, "period_end": None, "quarter": "Q4FY26", "page": 3}
    assert rs.resolve(trend, [done], synthetic_fin(FY26), date(2026, 3, 31))["source"] == "unverifiable"


def test_dropped_only_after_later_calls_were_searched():
    t = th.thread([[commit("A", "Q1FY26", date(2025, 6, 30), metric="milestone", tgt=target("none", None, None, "none", "none"),
                           subject="VAE plant start", end=None)]], "X")
    later = lambda q, qe, s: {"quarter": q, "quarter_end": qe, "sentences": [{"sentence": s}]}
    th.mark_dropped(t, [later("Q2FY26", date(2025, 9, 30), "Paint demand was soft.")], lambda _: False)
    assert t[0]["dropped"] and t[0]["searched_later"] == ["Q2FY26"]
    th.mark_dropped(t, [later("Q2FY26", date(2025, 9, 30), "The VAE line is on schedule.")], lambda _: False)
    assert not t[0]["dropped"] and t[0]["mentioned_later"] == ["Q2FY26"]
    th.mark_dropped(t, [], lambda _: False)
    assert not t[0]["dropped"]                                                   # nothing later to search


# --- resolve ---------------------------------------------------------------------------------
def test_pbdit_both_definitions_and_calibration(fx):
    """Asian Paints Q2 FY26 standalone: management said 18.5% -> the definition WITHOUT other income."""
    qe = date(2025, 9, 30)
    df = fin.add_derived(pd.DataFrame([fin.parse_xbrl(fx("xbrl_asianpaint_2025-09_standalone.xml"), qe, "u")]))
    got = rs.compute("pbdit_margin", df, [qe])
    assert got["values"]["with_other_income"] == pytest.approx(21.63, abs=0.01)
    assert got["values"]["without_other_income"] == pytest.approx(18.48, abs=0.01)
    assert {r["field"] for r in got["receipts"]} >= {"pbt", "other_income", "revenue"}
    f = rs.Financials("ASIANPAINT", loader=lambda s, n, b: df.assign(basis=b))
    fact = {"kind": "value", "value": 18.5, "period_end": qe, "basis": "standalone", "quarter": "Q2FY26", "page": 27}
    cal = rs.calibrate([fact], f)
    assert (cal["basis"], cal["definition"]) == ("standalone", "without_other_income")


def synthetic_fin(quarters, revenue=1000e7, ebit=190e7):
    rows = [{"qe": q, "basis": "Consolidated", "revenue": revenue, "pbt": ebit, "finance_costs": 0.0, "dep_amort": 0.0,
             "other_income": 0.0, "pat": 100e7, "receipts": {}} for q in quarters]
    df = pd.DataFrame(rows)
    return rs.Financials("X", loader=lambda s, n, b: df.assign(basis=b))


def test_fy_target_needs_all_four_quarters():
    t = th.thread([[commit("A", "Q1FY26", date(2025, 6, 30))]], "X")[0]
    assert rs.resolve(t, [], synthetic_fin(FY26), date(2026, 3, 31))["final"] == pytest.approx(19.0)
    partial = rs.resolve(t, [], synthetic_fin(FY26[:2]), date(2025, 9, 30))
    assert partial["final"] is None and partial["interim"] == pytest.approx(19.0)


def test_inr_target_far_from_company_figure_is_not_resolved():
    tg = target("range", 1200.0, 1500.0, "inr_cr")
    t = th.thread([[commit("A", "Q1FY26", date(2025, 6, 30), metric="revenue_growth", tgt=tg)]], "X")[0]
    res = rs.resolve(t, [], synthetic_fin(FY26, revenue=10_000e7), date(2026, 3, 31))   # company: 40,000 cr
    assert res["source"] == "unverifiable" and "part of the business" in res["note"]


# --- verdicts --------------------------------------------------------------------------------
@pytest.mark.parametrize("tgt,actual,metric,ok", [
    (target(), 19.5, "pbdit_margin", True),
    (target(), 21.0, "pbdit_margin", True),                                    # above a band: beat
    (target(), 17.9, "pbdit_margin", False),
    (target(low=700.0, high=800.0, unit="inr_cr"), 900.0, "capex", False),     # capex over range is not a beat
    (target("value", 10.0, None, "pct", "about"), 10.8, "volume_growth", True),
    (target("value", 10.0, None, "pct", "at_most"), 10.8, "debt", False),
    (target("direction", None, None, "pct", "up"), 0.4, "ebitda_margin", True),
])
def test_meets(tgt, actual, metric, ok):
    assert vd.meets(tgt, actual, metric)[0] is ok


def test_decide_rules():
    t = th.thread([[commit("A", "Q1FY26", date(2025, 6, 30))]], "X")[0]
    asof = date(2026, 3, 31)
    assert vd.decide(t, {"final": 19.0}, asof)[0] == "Kept"
    assert vd.decide(t, {"final": 17.0}, asof)[0] == "Missed"
    assert vd.decide(t, {"final": None, "interim": 19.0}, date(2025, 9, 30))[0] == "On track"
    assert vd.decide(t, {"final": None, "interim": 15.0}, date(2025, 9, 30)) == ("Pending", "interim actual off target")
    assert vd.decide(t, {"final": None, "note": "no data"}, asof)[0] == "Unverifiable"
    assert vd.decide(t | {"dropped": True, "searched_later": ["Q2FY26"]}, {"final": None}, asof)[0] == "Dropped"
    m = th.thread([[commit("M", "Q1FY26", date(2025, 6, 30), metric="milestone", tgt=target("none", None, None, "none", "none"))]], "X")[0]
    assert vd.decide(m, {"final": "event_delayed"}, asof)[0] == "Missed"


def test_explanation_with_invented_number_is_replaced(fake_llm):
    fake_llm([json.dumps({"lines": [{"id": "A", "line": "Margin came in at 19.5%, well within the band."},
                                    {"id": "B", "line": "Margin hit 25% thanks to price cuts."}]})])
    facts = [{"id": i, "promise": "18-20% band", "target": "18–20%", "due": "2026-03-31", "actual": 19.5,
              "source": "xbrl", "verdict": "Kept", "rule": "within range"} for i in "AB"]
    lines = vd.explain(facts, "X")
    assert lines["A"].startswith("Margin came in") and lines["B"].startswith("Kept: target 18–20%")


# --- eval ------------------------------------------------------------------------------------
def test_eval_precision_recall(tmp_path):
    g = pd.DataFrame([
        {"id": "X-Q1FY27-001", "quarter": "Q1FY27", "sentence": "We keep 18-20%.", "is_promise": "Y", "metric": "pbdit_margin"},
        {"id": "X-Q1FY27-002", "quarter": "Q1FY27", "sentence": "Demand will improve.", "is_promise": "N", "metric": ""},
        {"id": "X-Q1FY27-003", "quarter": "Q1FY27", "sentence": "Capex Rs 700 crores.", "is_promise": "Y", "metric": "capex"},
        {"id": "", "quarter": "Q1FY27", "sentence": "Plant starts in Q3.", "is_promise": "Y", "metric": "milestone"},
        {"id": "X-Q1FY27-004", "quarter": "Q1FY27", "sentence": "Unlabelled.", "is_promise": "", "metric": ""},
    ]).reindex(columns=["id", "quarter", "page", "speaker", "sentence", "is_promise", "metric", "target", "horizon",
                        "conditional", "notes"]).astype(object).fillna("")
    g.to_csv(tmp_path / "candidates_X.csv", index=False)
    cls = [{"id": "X-Q1FY27-001", "quarter": "Q1FY27", "sentence": "We keep 18-20%.", "is_commitment": True, "metric": "pbdit_margin"},
           {"id": "X-Q1FY27-002", "quarter": "Q1FY27", "sentence": "Demand will improve.", "is_commitment": True},
           {"id": "X-Q1FY27-003", "quarter": "Q1FY27", "sentence": "Capex Rs 700 crores.", "is_commitment": False}]
    (tmp_path / "X.json").write_text(json.dumps({"calls": [{"quarter": "Q1FY27"}], "classified": cls}))
    r = ev.evaluate(tmp_path / "candidates_X.csv", tmp_path / "X.json")
    assert (r["tp"], r["fp"], r["fn"]) == (1, 1, 2)
    assert r["precision"] == 0.5 and r["recall"] == pytest.approx(1 / 3)
    assert (r["missed_at_candidate_filter"], r["missed_at_classifier"]) == (1, 1)
    assert r["metric_agreement"] == 1.0


def test_eval_reports_unlabelled(tmp_path, capsys):
    pd.DataFrame([{"id": "a", "quarter": "Q1FY27", "sentence": "s", "is_promise": "", "metric": ""}]).to_csv(
        tmp_path / "candidates_X.csv", index=False)
    assert ev.main(tmp_path, tmp_path) == 0
    assert "golden set not labelled yet" in capsys.readouterr().out
