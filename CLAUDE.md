# FINN — Financial Investment Agent (build challenge)

## What we're building
Mobile-first investing agent for Indian equities (NSE/BSE).
- Push: windowed digest of corporate filings across a 15–20 stock portfolio, ranked by
  materiality; configurable alerts on end-of-day price/volume.
- Pull: on-demand research on ANY NSE ticker, grounded ONLY in primary sources
  (annual reports + concall transcripts). Hero feature: "promise ledger" —
  management guidance vs. what was actually delivered, with verbatim receipts.
Thesis: "FINN reads everything so you only read what could change your mind."
Graded on judgment, architecture, creativity, cost-efficiency — not completeness.

## Current phase: CORE ENGINE (still no UI)
Spikes are done (see spikes/*/REPORT.md, docs/SPIKES_SUMMARY.md). Decision: NSE-only.
Now: promote spike code into the finn/ package, then build the promise-ledger engine as a CLI.
- finn/data/   : source clients (one module per source), cache, rate limiter
- finn/ledger/ : promise extraction, threading, resolution, verdicts
- finn/llm.py  : the ONLY place that calls a model (routing, cache, cost log)
- tests/       : run offline against recorded fixtures from data/raw
Every number carries a receipt (XBRL tag + URL); every quote carries page + speaker and must
be found verbatim (after normalisation) in the source text, or it is discarded.

## Rules
- Python 3.11+, requests + pandas. Playwright only if plain HTTP genuinely fails.
- Be polite to sources: ≤1 request/sec, realistic User-Agent, reuse sessions,
  cache every download in data/raw/ keyed by URL hash; never re-download.
- Never invent data. Missing field → say so in the report.
- Financial numbers come from structured sources (XBRL / tables), never from an LLM.
- Secrets only in .env (gitignored). Never print keys.
- Ask before adding heavy dependencies or restructuring the project.
- Small readable scripts over frameworks at this stage.
