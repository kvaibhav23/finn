"""Website data: status ledgers for any ticker, display-ready slimming, title guard."""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_web_data as bw  # noqa: E402

from finn.ledger import __main__ as cli  # noqa: E402
from finn.ledger import render  # noqa: E402
from tests.test_ledger import commit, target  # noqa: E402


def test_no_transcripts_writes_a_status_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "OUT", tmp_path)
    monkeypatch.setattr(cli, "load_calls", lambda symbol, n: [])
    monkeypatch.setattr(cli, "company_name", lambda s: "Tiny Co Limited")
    L = cli.run("TINYCO", 6)
    saved = json.loads((tmp_path / "TINYCO.json").read_text())
    assert L["status"] == saved["status"] == "no_transcripts" and saved["name"] == "Tiny Co Limited"
    assert "No earnings-call transcripts" in saved["message"]


def test_failed_run_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "OUT", tmp_path)
    monkeypatch.setattr(cli, "company_name", lambda s: None)
    def boom(*a, **k):
        raise RuntimeError("NSE returned 403")
    monkeypatch.setattr(cli, "run", boom)
    monkeypatch.setattr(sys, "argv", ["finn.ledger", "abc"])
    with pytest.raises(SystemExit):
        cli.main()
    saved = json.loads((tmp_path / "ABC.json").read_text())
    assert saved["status"] == "failed" and "NSE returned 403" in saved["message"]


def ledger_with(promise_quote="we keep the 18 to 20% band", subject="margin band of 25%"):
    v = commit("A", "Q1FY26", date(2025, 6, 30), quote=promise_quote, subject=subject) | {"status": "New"}
    p = {"id": "A", "metric": "pbdit_margin", "scope": "segment", "versions": [v], "verdict": "Kept", "rule": "within range",
         "explanation": "Within the band.", "searched_later": [],
         "resolution": {"source": "xbrl", "final": 19.53, "basis": "consolidated", "definition": "without_other_income",
                        "detail": {"receipts": [{"xbrl_url": "https://x/1.xml"}], "formulas": {"without_other_income": "f"}}}}
    return {"symbol": "X", "name": "X Ltd", "status": "ok", "generated_at": "2026-11-01T00:00:00", "as_of_results": "2026-09-30",
            "calls": [{"quarter": "Q1FY26", "quarter_end": "2025-06-30", "pdf_url": "https://x/t.pdf"}],
            "promises": [p], "classified": [{}] * 40, "rejected": [{}], "cost": {"total_inr": 1.234}}


def test_slim_is_display_ready():
    s = bw.slim(ledger_with())
    p = s["promises"][0]
    assert "classified" not in s and s["candidates"] == 40 and s["cost_inr"] == 1.23
    assert p["pdf_url"] == "https://x/t.pdf" and p["actual"]["text"] == "19.53%" and p["actual"]["link"] == "https://x/1.xml"
    assert p["actual"]["definition"] == "without other income" and p["due"] == "2026-03-31"
    assert p["title"] == "PBDIT margin 18–20%"     # subject "25%" is not in the quote: falls back to the metric


def test_title_uses_subject_when_its_numbers_were_said():
    s = bw.slim(ledger_with(subject="mobile margin band"))
    assert s["promises"][0]["title"] == "Mobile margin band 18–20%"


def test_build_writes_index_and_status_ledgers(tmp_path):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "X.json").write_text(json.dumps(ledger_with(), default=str))
    (tmp_path / "in" / "Y.json").write_text(json.dumps({"symbol": "Y", "name": None, "status": "no_transcripts",
                                                        "generated_at": "t", "message": "none"}))
    out = tmp_path / "out"
    out.mkdir()
    (out / "symbols.json").write_text(json.dumps([["X", "X Ltd"], ["Y", "Y Industries"]]))
    idx = {i["symbol"]: i for i in bw.build(tmp_path / "in", out, tmp_path / "market")}
    assert idx["X"]["counts"]["Kept"] == 1 and idx["Y"]["status"] == "no_transcripts" and idx["Y"]["name"] == "Y Industries"
    assert json.loads((out / "ledgers" / "Y.json").read_text())["promises"] == []


def test_bank_nan_revenue_cannot_be_compared():
    import pandas as pd
    from finn.ledger import resolve as rs
    q = [date(2025, 6, 30)]
    df = pd.DataFrame([{"qe": q[0], "revenue": float("nan"), "pbt": 1e9, "finance_costs": 0.0, "dep_amort": 0.0,
                        "other_income": 0.0, "receipts": {}}])
    assert rs.compute("pbdit_margin", df, q) is None


def test_market_banner_lists_the_biggest_movers(tmp_path):
    (tmp_path / "_market.json").write_text(json.dumps({"date": "2026-11-02", "close": 23000.0,
                                                       "change_pct": -2.4, "big": True}))
    index = [{"symbol": s, "name": s, "price_as_of": d, "change_pct": c} for s, d, c in
             [("A", "2026-11-02", -1.0), ("B", "2026-11-02", -6.5), ("C", "2026-11-02", 3.0), ("D", "2026-10-30", -9.0)]]
    b = bw.market_banner(tmp_path, index, top=2)
    assert b["big"] and [m["symbol"] for m in b["movers"]] == ["B", "C"]   # D's price is from another day
    assert bw.market_banner(tmp_path / "none", index) is None


def test_spark_keeps_first_and_last_close_and_thins_the_rest():
    rows = [[f"d{i}", float(i), 1, None] for i in range(250)]
    s = bw.spark(rows)
    assert s[0] == 0.0 and s[-1] == 249.0
    assert 50 <= len(s) <= 60
    assert s == sorted(s)
    assert bw.spark([["d", 1.0, 1, None]]) == []
    assert bw.spark(None) == []
