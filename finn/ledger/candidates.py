"""Stage 1: candidate sentences. Same parser, cues and ids as the golden export, so eval can join."""
from __future__ import annotations

from datetime import date, timedelta

from finn.data import http
from finn.data import transcripts as tr

from .periods import fy_label


def load_calls(symbol: str, n: int, today: date | None = None, client: http.Client | None = None) -> list[dict]:
    """Last n earnings calls, oldest first: {symbol, quarter, quarter_end, pdf_url, text, sentences, candidates}.
    `sentences` = every verbatim management sentence (searched by thread/resolve);
    `candidates` = the forward-looking subset, with the previous sentence as context."""
    c = client or http.client()
    today = today or http.today_ist()
    found = tr.find_transcripts(symbol, today - timedelta(days=30 * (3 * n + 4)), today, client=c).tail(n)
    calls = []
    for _, r in found.iterrows():
        q = fy_label(r["quarter_end"])
        parsed = tr.parse_transcript(c.get(r["pdf_url"], policy="permanent").raise_for_status().content)
        sentences, candidates, k = [], [], 0
        for i, s in enumerate(tr.management_sentences(parsed, pattern=None)):
            s = s | {"sid": f"{symbol}-{q}-s{i:04d}"}
            if tr.FORWARD_BROAD.search(s["sentence"]):
                k += 1
                prev = sentences[-1]["sentence"] if sentences and sentences[-1]["speaker"] == s["speaker"] else ""
                candidates.append(s | {"id": f"{symbol}-{q}-{k:03d}", "context": prev})
            sentences.append(s)
        calls.append({"symbol": symbol, "quarter": q, "quarter_end": r["quarter_end"], "pdf_url": r["pdf_url"],
                      "text": parsed["text"], "warnings": parsed["warnings"],
                      "sentences": sentences, "candidates": candidates})
    return calls
