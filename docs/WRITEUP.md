# FINN: covering note

**Prototype:** https://finn-six-roan.vercel.app (open on a phone)
**Repository:** https://github.com/kvaibhav23/finn
**AI build history:** `docs/build-history/` in the repository (the full Claude Code conversation, secrets removed)

This is a few days past the 1 November deadline; I used the extra time to close the gaps against the brief listed
below rather than send something that didn't meet it.

## What I built

FINN is a mobile web app that reads NSE for you.

**Push.**
- **Digest:** every filing from a 20-company portfolio, for a window you choose (24 hours by default), most important first.
  - **Ranking:** results, people changes, deals, and anything a regulator, auditor, lender or rating agency did come first. Routine paperwork is counted, not shown.
  - **Results filings** carry Revenue, EBITDA, PBT and PAT against the previous quarter and the same quarter last year, from the company's XBRL.
  - **Management changes** carry the appointee's profile, read from the filing.
- **Alerts:** your own thresholds for an unusual day (±X% price, N× the 50-day volume) and the filing types you care about. Email and WhatsApp delivery is built and waits on sending accounts.

**Pull.** The promise ledger answers the brief's worked example directly. FINN reads six quarters of earnings-call transcripts, keeps the forward-looking things management committed to, follows each one across calls, and checks it against filed results. Each promise gets a verdict: Kept, Missed, On track, Revised, Dropped, Pending or Unverifiable.

Dixon Technologies has 186 promises. Each shows:
- the quote;
- the transcript page;
- every later mention;
- the XBRL figure it was checked against.

**Analyse** runs the same engine on any NSE company.

## Key decisions

- **The model reads; code decides.** Gemini Flash-Lite only sorts sentences and copies words.
  - Each quote must appear verbatim in the source, and each number in a target must appear in its quote.
  - Actuals come from XBRL tags or formulas over them.
  - Verdicts come from fixed rules.

  This costs some recall, but every claim can be checked by clicking it, which matters more to an investor than coverage.
- **A cheap model, used everywhere, and cached.** The task is narrow, so a bigger model buys little. 499 calls so far: ₹69 at paid rates, ₹0 on the free tier.
- **NSE only, plain HTTP, polite.** The spikes showed every need (prices, filings, XBRL, transcripts) is served by NSE without a browser or OCR. BSE blocks plain requests, so it was left out.
- **No server database.** GitHub Actions rebuilds the data every two hours through the day, commits static JSON, and Vercel serves it from Mumbai. Cheap, auditable (every update is a commit) and fast.
- **Appointee profiles from the filing, not LinkedIn.** SEBI's Reg 30 disclosure already carries a "brief profile". LinkedIn's terms forbid scraping, and the filing is the primary source.
- **No chat box.** A chat interface invites answers no one can check. FINN's interaction is: rank what changed, let you set what "unusual" means, and make every line open its evidence. It works in 7 Indian languages because the people this helps most don't all read English.
- **No buy/sell calls.** Those need SEBI Research Analyst registration. FINN states facts and lets the investor judge.

## What I left out, deliberately

- **Four of the eight pull items:** business snapshot, balance sheet, cash quality, and bull vs bear. I chose depth on narrative vs numbers, which the brief values most, over breadth. Bull vs bear in particular is where a model starts writing opinion.
- **Annual reports.** The client is built and tested (spike 06), but the ledger reads transcripts plus XBRL only. Annual-report text is the next source to add.
- **Live prices** (they need a paid licensed feed), and **news** and **broker notes** (the brief excludes them).
- **OCR:** scanned filings with no text layer get a link instead of a profile.

## Where I'd take it next

1. **Annual reports in the ledger:** capex and segment promises made in the chairman's letter, checked against the next report.
2. **Cash quality and balance sheet** from the half-yearly XBRL (cash-flow statement, debt), with the same receipts.
3. **Personal portfolios:** your holdings instead of a fixed 20, with alerts delivered on WhatsApp.
4. **A promise-level push:** "management's FY27 margin target is now off track after these results", sent the evening results come out.
5. **Evaluation at scale:** a labelled set of promises across 30 companies to measure extraction precision and recall over time (a first golden set is in `docs/golden/`).
