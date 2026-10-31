"""Spike 05: quarterly financials from XBRL (no PDFs, no LLM).

Sources (both list filings with an XBRL link per quarter x consolidated/standalone):
  - /api/integrated-filing-results?type=Integrated Filing- Financials   (Mar-2025 onwards)
  - /api/corporates-financial-results?period=Quarterly                  (legacy, up to Dec-2024)
Facts are picked by period dates (quarter = duration ending on the quarter-end, ~3 months,
no dimensions), not by context ids, so the parser survives format differences (banks etc.).
"""
import io
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from lxml import etree

from common import fetch, log_summary, make_session
from tickers import SAMPLE

IF_API = "https://www.nseindia.com/api/integrated-filing-results"
LEGACY_API = "https://www.nseindia.com/api/corporates-financial-results"
ANN_API = "https://www.nseindia.com/api/corporate-announcements"
XBRLI = "{http://www.xbrl.org/2003/instance}"
N_QUARTERS = 4

LINE_ITEMS = {  # output name -> candidate XBRL local names (first present wins)
    "revenue": ["RevenueFromOperations"],
    "other_income": ["OtherIncome"],
    "total_income": ["Income"],
    "interest_earned": ["InterestEarned"],          # banks
    "interest_expended": ["InterestExpended"],      # banks
    "employee_cost": ["EmployeeBenefitExpense", "EmployeesCost"],
    "finance_costs": ["FinanceCosts"],
    "dep_amort": ["DepreciationDepletionAndAmortisationExpense"],
    "total_expenses": ["Expenses", "OperatingExpenses"],
    "provisions": ["ProvisionsOtherThanTaxAndContingencies"],  # banks
    "pbt": ["ProfitBeforeTax", "ProfitLossFromOrdinaryActivitiesBeforeTax"],
    "tax": ["TaxExpense"],
    "pat": ["ProfitLossForPeriod", "ProfitLossForThePeriod"],
    "pat_owners": ["ProfitOrLossAttributableToOwnersOfParent",
                   "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates"],
    "eps_basic": ["BasicEarningsLossPerShareFromContinuingOperations",
                  "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
                  "BasicEarningsPerShareAfterExtraordinaryItems"],
    "gross_npa_pct": ["PercentageOfGrossNpa"],      # banks
}


def parse_xbrl(content: bytes, quarter_end: date) -> tuple[dict, dict]:
    """-> (line items for the quarter, info). Values exactly as tagged; INR or INR/share."""
    root = etree.fromstring(content)
    quarter_ctx, ctx_start = set(), {}
    for c in root.iter(f"{XBRLI}context"):
        if any(m.tag.endswith(("explicitMember", "typedMember")) for m in c.iter()):
            continue
        p = c.find(f"{XBRLI}period")
        s, e = p.findtext(f"{XBRLI}startDate"), p.findtext(f"{XBRLI}endDate")
        if s and e and date.fromisoformat(e.strip()) == quarter_end \
                and 80 <= (date.fromisoformat(e.strip()) - date.fromisoformat(s.strip())).days <= 95:
            quarter_ctx.add(c.get("id"))
            ctx_start[c.get("id")] = s.strip()
    # Legacy files mislabel the YTD context ("FourD") with quarter dates. Trust the filing's
    # own DateOfStartOfReportingPeriod fact over the context's declared period.
    for el in root:
        if isinstance(el.tag, str) and etree.QName(el).localname == "DateOfStartOfReportingPeriod" \
                and el.get("contextRef") in quarter_ctx and (el.text or "").strip() != ctx_start[el.get("contextRef")]:
            quarter_ctx.discard(el.get("contextRef"))
    facts = {}
    for el in root:
        if not isinstance(el.tag, str) or el.get("contextRef") not in quarter_ctx:
            continue
        facts.setdefault(etree.QName(el).localname, (el.text or "").strip())
    out, found_tag = {}, {}
    for name, candidates in LINE_ITEMS.items():
        for tag in candidates:
            if tag in facts and facts[tag] != "":
                out[name] = float(facts[tag])
                found_tag[name] = tag
                break
    # Consolidated bank filings tag asset-quality ratios as 0 = "not reported here".
    if out.get("gross_npa_pct") == 0 and facts.get("NatureOfReportStandaloneConsolidated") == "Consolidated":
        out.pop("gross_npa_pct")
        found_tag["gross_npa_pct"] = "0 in consolidated -> treated as not reported"
    ns = sorted({etree.QName(el).namespace.rsplit("/", 2)[-2] for el in root
                 if isinstance(el.tag, str) and el.get("contextRef")})
    return out, {"quarter_contexts": sorted(quarter_ctx), "n_quarter_facts": len(facts),
                 "tags": found_tag, "ns": ns, "rounding": facts.get("LevelOfRounding"),
                 "audited": facts.get("WhetherResultsAreAuditedOrUnaudited"),
                 "board_meeting": facts.get("DateOfBoardMeetingWhenFinancialResultsWereApproved")}


def list_filings(symbol: str) -> pd.DataFrame:
    s = make_session("nse")
    rows = []
    f = fetch(s, IF_API, params={"index": "equities", "symbol": symbol,
                                 "type": "Integrated Filing- Financials", "page": 1, "size": 20})
    if f.ok:
        for r in f.json().get("data", []):
            rows.append({"source": "integrated", "qe": datetime.strptime(r["qe_Date"], "%d-%b-%Y").date(),
                         "basis": r["consolidated"], "audited": r["audited"], "type_sub": r.get("type_Sub"),
                         "filed": r["broadcast_Date"], "xbrl": r["xbrl"]})
    else:
        print(f"  {symbol} integrated list FAIL {f.status}")
    f = fetch(s, LEGACY_API, params={"index": "equities", "period": "Quarterly", "symbol": symbol})
    if f.ok:
        for r in f.json():
            rows.append({"source": "legacy", "qe": datetime.strptime(r["toDate"], "%d-%b-%Y").date(),
                         "basis": "Consolidated" if r["consolidated"] == "Consolidated" else "Standalone",
                         "audited": r["audited"], "type_sub": r.get("format"),
                         "filed": r["filingDate"], "xbrl": r["xbrl"]})
    else:
        print(f"  {symbol} legacy list FAIL {f.status}")
    return pd.DataFrame(rows)


def pick_quarters(filings: pd.DataFrame, n: int) -> pd.DataFrame:
    """Latest n quarters; consolidated preferred; latest filing wins (revisions)."""
    f = filings.assign(pref=(filings["basis"] != "Consolidated").astype(int))
    f = f.sort_values(["qe", "pref", "filed"], ascending=[False, True, False])
    return f.drop_duplicates("qe").head(n)


def crore(v: float) -> str:
    return f"{v / 1e7:,.0f}"


def spot_check_pdf(symbol: str, board_meeting_day: str, values: dict):
    """Mechanical cross-check: does the results PDF contain the XBRL numbers (in crore)?"""
    import pymupdf
    ann = fetch(make_session("nse"), ANN_API, params={"index": "equities", "symbol": symbol,
                                                      "from_date": "01-10-2026", "to_date": "31-10-2026"})
    if not ann.ok:
        print("  announcements unavailable"); return
    cands = [a for a in ann.json() if a["desc"] == "Outcome of Board Meeting" and a["an_dt"].startswith(board_meeting_day)]
    if not cands:
        print("  no board-meeting outcome found"); return
    pdf = fetch(make_session("plain"), cands[0]["attchmntFile"])
    if not pdf.ok:
        print(f"  pdf FAIL {pdf.status}"); return
    doc = pymupdf.open(stream=pdf.content, filetype="pdf")
    text = "".join(p.get_text() for p in doc)
    print(f"  PDF {cands[0]['attchmntFile'].rsplit('/', 1)[-1]}: {doc.page_count} pages, {len(text):,} chars")
    for name, v in values.items():
        western = f"{v / 1e7:,.0f}"
        n = f"{v / 1e7:.0f}"
        indian = (n[:-3] and re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", n[:-3]) + "," + n[-3:]) or n
        hit = [s for s in {western, indian} if s in text]
        print(f"    {name}: XBRL {v:,.0f} INR = {western} cr -> found in PDF as {hit or 'NOT FOUND'}")


def main():
    all_rows, coverage = [], []
    for sym in SAMPLE:
        print(f"\n== {sym} ==")
        filings = list_filings(sym)
        if filings.empty:
            continue
        by_src = filings.groupby("source")["qe"].agg(["min", "max", "count"])
        print(by_src.to_string())
        coverage.append({"symbol": sym, **{f"{k}_{c}": v for k, row in by_src.iterrows() for c, v in row.items()}})
        for _, q in pick_quarters(filings, N_QUARTERS).iterrows():
            f = fetch(make_session("plain"), q["xbrl"])
            if not f.ok:
                print(f"  {q['qe']} XBRL FAIL {f.status}")
                continue
            items, info = parse_xbrl(f.content, q["qe"])
            missing = [k for k in LINE_ITEMS if k not in items]
            print(f"  {q['qe']} {q['basis'][:4]} {q['source']:10} {len(f.content)/1024:,.0f} KB "
                  f"ctx={info['quarter_contexts']} facts={info['n_quarter_facts']} ns={info['ns']} "
                  f"rounding={info['rounding']} {info['audited']} board={info['board_meeting']}")
            all_rows.append({"symbol": sym, "qe": q["qe"], "basis": q["basis"], **items,
                             "_missing": ",".join(missing), "_tags": info["tags"]})

    df = pd.DataFrame(all_rows)
    print("\n== line items (INR crore; EPS in INR) ==")
    show = df.copy()
    for c in LINE_ITEMS:
        if c in show and c not in ("eps_basic", "gross_npa_pct"):
            show[c] = show[c].map(lambda v: crore(v) if pd.notna(v) else "")
    cols = ["symbol", "qe", "basis", "revenue", "interest_earned", "total_income", "total_expenses",
            "pbt", "pat", "pat_owners", "eps_basic"]
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(show[[c for c in cols if c in show]].to_string(index=False))
    print("\nfill rate per line item:")
    print((df[[c for c in LINE_ITEMS if c in df]].notna().mean() * 100).round(0).astype(int).to_string())
    print("\nmissing per row:")
    print(df[["symbol", "qe", "_missing"]].to_string(index=False))

    print("\n== legacy format (Dec-2024, consolidated): does the same parser work? ==")
    for sym in ("TCS", "HDFCBANK"):
        leg = list_filings(sym)
        leg = leg[(leg["source"] == "legacy") & (leg["qe"] == date(2024, 12, 31)) & (leg["basis"] == "Consolidated")]
        if leg.empty:
            print(f"  {sym}: no legacy consolidated Dec-2024 filing listed"); continue
        f = fetch(make_session("plain"), leg.iloc[0]["xbrl"])
        if not f.ok:
            print(f"  {sym}: XBRL FAIL {f.status}"); continue
        items, info = parse_xbrl(f.content, date(2024, 12, 31))
        print(f"  {sym}: {len(f.content)/1024:,.0f} KB ctx={info['quarter_contexts']} ns={info['ns']} "
              f"rounding={info['rounding']} missing={[k for k in LINE_ITEMS if k not in items]}")
        print(f"    revenue={crore(items['revenue']) if 'revenue' in items else '-'} "
              f"interest_earned={crore(items['interest_earned']) if 'interest_earned' in items else '-'} "
              f"pat={crore(items['pat']) if 'pat' in items else '-'} eps={items.get('eps_basic')}")

    print("\n== spot check vs results PDF (TCS, Q2 FY27) ==")
    tcs = df[(df["symbol"] == "TCS") & (df["qe"] == date(2026, 9, 30))]
    if len(tcs):
        r = tcs.iloc[0]
        spot_check_pdf("TCS", "08-Oct-2026", {"revenue": r["revenue"], "pat": r["pat"]})

    print("\n" + log_summary())


if __name__ == "__main__":
    main()
