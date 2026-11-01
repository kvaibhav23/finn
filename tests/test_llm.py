"""finn/llm.py: cache, strict JSON with one repair retry, cost log, rate limits, key hygiene."""
import json

import pytest
from pydantic import BaseModel

from finn import llm


class Out(BaseModel):
    ok: bool
    n: int


def test_cache_hit_makes_no_call_and_costs_nothing(fake_llm):
    fake = fake_llm(['{"ok": true, "n": 3}'])
    assert llm.call("classify", "p", Out, symbol="X") == Out(ok=True, n=3)
    assert llm.call("classify", "p", Out, symbol="X") == Out(ok=True, n=3)   # no reply left: must be cached
    rows = [json.loads(l) for l in llm.COST_LOG.read_text().splitlines()]
    assert [r["cached"] for r in rows] == [False, True] and rows[1]["inr"] == 0.0
    assert len(fake.prompts) == 1


def test_invalid_json_gets_one_repair_retry(fake_llm):
    fake = fake_llm(['{"ok": "maybe"}', '{"ok": false, "n": 1}'])
    assert llm.call("classify", "p", Out) == Out(ok=False, n=1)
    assert "did not match the JSON schema" in fake.prompts[1]
    assert llm.cost_summary()["by_stage"]["classify"]["tokens_in"] == 2000   # both attempts are paid for


def test_second_invalid_reply_raises(fake_llm):
    fake_llm(["not json", '{"ok": 1}'])
    with pytest.raises(llm.LLMError):
        llm.call("classify", "p", Out)
    assert json.loads(llm.COST_LOG.read_text().splitlines()[-1])["failed"] is True


def test_cost_in_rupees():
    assert llm.inr("gemini-3.1-flash-lite", 1_000_000, 1_000_000) == pytest.approx((0.25 + 1.50) * llm.USD_INR)


def test_rate_limit_spacing_and_429_backoff(fake_llm):
    err = Exception("429 RESOURCE_EXHAUSTED ... Please retry in 2.5s.")
    err.code = 429
    fake = fake_llm([err, '{"ok": true, "n": 1}', '{"ok": true, "n": 2}'])
    llm.call("classify", "a", Out)
    llm.call("classify", "b", Out)
    assert 3.5 in fake.clock.sleeps                                  # waited the stated delay + 1 s
    assert all(s <= llm.MIN_INTERVAL for s in fake.clock.sleeps if s != 3.5)
    assert len(fake.prompts) == 3


def test_server_overload_is_retried_then_raised(fake_llm):
    busy = Exception("503 UNAVAILABLE high demand")
    busy.code = 503
    fake = fake_llm([busy, '{"ok": true, "n": 1}'])
    assert llm.call("classify", "a", Out).n == 1 and 10.0 in fake.clock.sleeps
    fake_llm([busy] * (llm.MAX_RETRIES + 1))
    with pytest.raises(Exception, match="503"):
        llm.call("classify", "b", Out)


def test_key_is_never_logged(fake_llm, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sk-SECRET-123")
    fake_llm(['{"ok": true, "n": 3}'])
    llm.call("classify", "p", Out)
    assert "sk-SECRET-123" not in llm.COST_LOG.read_text()
    assert all("sk-SECRET-123" not in f.read_text() for f in llm.CACHE_DIR.iterdir())


def test_missing_key_is_a_clear_error(fake_llm, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY is not set"):
        llm._api_key()
