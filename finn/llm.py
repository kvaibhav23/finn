"""The ONLY place FINN calls a model: routing, disk cache, strict JSON, one repair retry, cost log.

The model classifies and copies text. It never supplies a number that code has not found in a
verbatim source quote, and it never decides a verdict (see finn/ledger/).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "llm_cache"
COST_LOG = ROOT / "data" / "ledger" / "cost_log.jsonl"

CHEAP = "gemini-3.1-flash-lite"     # cheapest Lite open to new keys (2.5 Lite: 404 for new users)
ROUTES = {"classify": CHEAP, "thread": CHEAP, "resolve": CHEAP, "explain": CHEAP}
# USD per 1M tokens (input, output incl. thinking), paid tier.
# Source: https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-01.
PRICES = {"gemini-3.1-flash-lite": (0.25, 1.50),
          "gemini-3.5-flash-lite": (0.30, 2.50)}
USD_INR = 94.95   # ECB reference rate 2026-10-30 (api.frankfurter.dev)
# The ₹ figures are paid-tier equivalents; on the free tier the charge is 0 but requests are capped
# (15/min per model), hence the spacing and the back-off below.
MIN_INTERVAL = 4.5
MAX_RETRIES = 3
SERVER_BACKOFF = (10.0, 30.0, 60.0)   # 500/503 "high demand" are transient

T = TypeVar("T", bound=BaseModel)
_client = None
_last_call = 0.0
sleep, clock = time.sleep, time.monotonic   # injectable for tests


class LLMError(RuntimeError):
    pass


def _api_key() -> str:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise LLMError("GEMINI_API_KEY is not set in .env")
    return key


def client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=_api_key())
    return _client


def set_client(c) -> None:
    """Tests inject a fake with .models.generate_content(model=, contents=, config=)."""
    global _client
    _client = c


def inr(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = PRICES.get(model, (float("nan"), float("nan")))
    return (tokens_in * p_in + tokens_out * p_out) / 1e6 * USD_INR


def _generate(model: str, prompt: str, schema: type[BaseModel]) -> tuple[str, int, int]:
    from google.genai import types
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=0,
                                      thinking_config=types.ThinkingConfig(thinking_level="minimal"))  # thinking is billed as output
    global _last_call
    for attempt in range(MAX_RETRIES + 1):
        wait = MIN_INTERVAL - (clock() - _last_call)
        if wait > 0:
            sleep(wait)
        _last_call = clock()
        try:
            r = client().models.generate_content(model=model, contents=prompt, config=cfg)
            break
        except Exception as e:  # google.genai.errors.APIError carries .code
            code = getattr(e, "code", None)
            if code not in (429, 500, 503) or attempt == MAX_RETRIES:
                raise
            m = re.search(r"retry in ([\d.]+)s", str(e))
            sleep((float(m[1]) + 1) if code == 429 and m else SERVER_BACKOFF[attempt])
    u = r.usage_metadata
    out = (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
    return r.text or "", getattr(u, "prompt_token_count", 0) or 0, out


def _log(**row) -> None:
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def call(stage: str, prompt: str, schema: type[T], symbol: str = "", model: str | None = None) -> T:
    """Strict-JSON call. Cached on disk by hash(model + schema + prompt); a cache hit costs 0."""
    model = model or ROUTES[stage]
    spec = json.dumps(schema.model_json_schema(), sort_keys=True)
    key = hashlib.sha256(f"{model}\n{spec}\n{prompt}".encode()).hexdigest()[:24]
    path = CACHE_DIR / f"{key}.json"
    base = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": stage, "symbol": symbol, "model": model, "key": key}
    if path.exists():
        hit = json.loads(path.read_text())
        _log(**base, tokens_in=hit["tokens_in"], tokens_out=hit["tokens_out"], cached=True, inr=0.0)
        return schema.model_validate(hit["output"])
    text, t_in, t_out = _generate(model, prompt, schema)
    try:
        out = schema.model_validate_json(text)
    except ValidationError as e:
        repair = (f"{prompt}\n\nYour previous reply did not match the JSON schema.\nReply:\n{text[:4000]}\n"
                  f"Errors:\n{str(e)[:2000]}\nReturn only the corrected JSON.")
        text, r_in, r_out = _generate(model, repair, schema)
        t_in, t_out = t_in + r_in, t_out + r_out
        try:
            out = schema.model_validate_json(text)
        except ValidationError as e2:
            _log(**base, tokens_in=t_in, tokens_out=t_out, cached=False, inr=inr(model, t_in, t_out), failed=True)
            raise LLMError(f"{stage}: invalid JSON after one repair retry: {str(e2)[:300]}") from e2
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": model, "stage": stage, "tokens_in": t_in, "tokens_out": t_out,
                                "output": out.model_dump(mode="json")}))
    _log(**base, tokens_in=t_in, tokens_out=t_out, cached=False, inr=inr(model, t_in, t_out))
    return out


def cost_summary(symbol: str | None = None, since: str | None = None) -> dict:
    """Totals from the cost log: {"by_stage": {stage: {...}}, "total_inr", "calls", "cached"}."""
    by = defaultdict(lambda: {"calls": 0, "cached": 0, "tokens_in": 0, "tokens_out": 0, "inr": 0.0})
    if COST_LOG.exists():
        for line in COST_LOG.read_text().splitlines():
            r = json.loads(line)
            if (symbol and r["symbol"] != symbol) or (since and r["ts"] < since):
                continue
            s = by[r["stage"]]
            s["calls"] += 1
            s["cached"] += r["cached"]
            if not r["cached"]:
                s["tokens_in"] += r["tokens_in"]
                s["tokens_out"] += r["tokens_out"]
                s["inr"] += r["inr"]
    return {"by_stage": dict(by), "total_inr": round(sum(s["inr"] for s in by.values()), 4),
            "calls": sum(s["calls"] for s in by.values()), "cached": sum(s["cached"] for s in by.values())}
