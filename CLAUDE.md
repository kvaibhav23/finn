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

## Current phase: DATA SPIKES (no product code, no UI)
Each spike lives in spikes/NN_name/ with:
- run.py (runnable: python spikes/NN_name/run.py)
- REPORT.md: what worked, what failed, HTTP status codes, latency, sample output,
  PASS/FAIL verdict, recommended fallback, proposed function signature.

## Rules
- Python 3.11+, requests + pandas. Playwright only if plain HTTP genuinely fails.
- Be polite to sources: ≤1 request/sec, realistic User-Agent, reuse sessions,
  cache every download in data/raw/ keyed by URL hash; never re-download.
- Never invent data. Missing field → say so in the report.
- Financial numbers come from structured sources (XBRL / tables), never from an LLM.
- Secrets only in .env (gitignored). Never print keys.
- Ask before adding heavy dependencies or restructuring the project.
- Small readable scripts over frameworks at this stage.
