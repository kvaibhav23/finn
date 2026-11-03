"""Quarterly financials from NSE XBRL, with a receipt (tag + file URL) for every number (spike 05).

Traps handled here:
  1. Legacy files put 9-month YTD values under a context dated as the quarter ("FourD"):
     contexts are validated against the filing's own DateOfStartOfReportingPeriod fact.
  2. Consolidated bank filings tag asset-quality ratios as 0 meaning "not reported": -> NaN + note.
  4. Banks use a different taxonomy: per-taxonomy tag maps and a `taxonomy` column.
  5. The legacy results listing stops at Dec-2024; newer quarters are Integrated Filings:
     list_filings() merges both.
Derived metrics are labelled with their formula and inputs; nothing is ever estimated.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from typing import Callable

import pandas as pd
from lxml import etree

from . import http

IF_API = "https://www.nseindia.com/api/integrated-filing-results"
LEGACY_API = "https://www.nseindia.com/api/corporates-financial-results"
XBRLI = "{http://www.xbrl.org/2003/instance}"

COMMON = {
    "other_income": ["OtherIncome"],
    "total_income": ["Income"],
    "tax": ["TaxExpense"],
    "paid_up_capital": ["PaidUpValueOfEquityShareCapital"],
    "face_value": ["FaceValueOfEquityShareCapital"],
}
TAGS = {
    "indas": {**COMMON,
              "revenue": ["RevenueFromOperations"],
              "employee_cost": ["EmployeeBenefitExpense"],
              "finance_costs": ["FinanceCosts"],
              "dep_amort": ["DepreciationDepletionAndAmortisationExpense"],
              "total_expenses": ["Expenses"],
              "pbt": ["ProfitBeforeTax"],
              "pat": ["ProfitLossForPeriod"],
              "pat_owners": ["ProfitOrLossAttributableToOwnersOfParent"],
              "eps_basic": ["BasicEarningsLossPerShareFromContinuingOperations",
                            "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"],
              "eps_diluted": ["DilutedEarningsLossPerShareFromContinuingOperations",
                              "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations"]},
    "banking": {**COMMON,
                "interest_earned": ["InterestEarned"],
                "interest_expended": ["InterestExpended"],
                "employee_cost": ["EmployeesCost"],
                "total_expenses": ["OperatingExpenses"],
                "provisions": ["ProvisionsOtherThanTaxAndContingencies"],
                "pbt": ["ProfitLossFromOrdinaryActivitiesBeforeTax"],
                "pat": ["ProfitLossForThePeriod"],
                "pat_owners": ["ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates"],
                "eps_basic": ["BasicEarningsPerShareAfterExtraordinaryItems"],
                "eps_diluted": ["DilutedEarningsPerShareAfterExtraordinaryItems"],
                "gross_npa_pct": ["PercentageOfGrossNpa"],
                "net_npa_pct": ["PercentageOfNpa"],
                "cet1_ratio": ["CET1Ratio"],
                "roa": ["ReturnOnAssets"]},
}
ZERO_MEANS_MISSING = ("gross_npa_pct", "net_npa_pct", "cet1_ratio", "roa")
VALUE_FIELDS = sorted({f for t in TAGS.values() for f in t})


# --- XBRL parsing ------------------------------------------------------------------------
def _quarter_contexts(root, quarter_end: date) -> set[str]:
    starts = {}
    for c in root.iter(f"{XBRLI}context"):
        if any(isinstance(m.tag, str) and m.tag.endswith(("explicitMember", "typedMember")) for m in c.iter()):
            continue
        s = c.findtext(f"{XBRLI}period/{XBRLI}startDate")
        e = c.findtext(f"{XBRLI}period/{XBRLI}endDate")
        if s and e and date.fromisoformat(e.strip()) == quarter_end \
                and 80 <= (quarter_end - date.fromisoformat(s.strip())).days <= 95:
            starts[c.get("id")] = s.strip()
    # Trap 1: trust the filing's own DateOfStartOfReportingPeriod over the context's declared dates.
    for el in root:
        if isinstance(el.tag, str) and etree.QName(el).localname == "DateOfStartOfReportingPeriod" \
                and el.get("contextRef") in starts and (el.text or "").strip() != starts[el.get("contextRef")]:
            starts.pop(el.get("contextRef"))
    return set(starts)


def parse_xbrl(content: bytes, quarter_end: date, url: str = "") -> dict:
    """One quarter's values (INR / INR per share, exactly as tagged) + receipts + notes."""
    root = etree.fromstring(content)
    ctx = _quarter_contexts(root, quarter_end)
    facts: dict[str, str] = {}
    for el in root:
        if isinstance(el.tag, str) and el.get("contextRef") in ctx:
            facts.setdefault(etree.QName(el).localname, (el.text or "").strip())
    taxonomy = "banking" if "InterestEarned" in facts else "indas"
    row = {"qe": quarter_end, "taxonomy": taxonomy, "xbrl_url": url,
           "basis": facts.get("NatureOfReportStandaloneConsolidated"),
           "audited": facts.get("WhetherResultsAreAuditedOrUnaudited"),
           "board_meeting": facts.get("DateOfBoardMeetingWhenFinancialResultsWereApproved"),
           "rounding": facts.get("LevelOfRounding")}
    receipts, notes = {}, []
    for field in VALUE_FIELDS:
        row[field] = math.nan
        for tag in TAGS[taxonomy].get(field, []):
            if facts.get(tag) not in (None, ""):
                row[field] = float(facts[tag])
                receipts[field] = {"tag": tag, "xbrl_url": url}
                break
    # Trap 2: consolidated bank filings tag asset-quality ratios as 0 = "not reported here".
    if taxonomy == "banking" and (row["basis"] or "").lower() == "consolidated":
        for field in ZERO_MEANS_MISSING:
            if row[field] == 0:
                row[field] = math.nan
                receipts.pop(field, None)
                notes.append(f"{field}: tagged 0 in consolidated bank filing -> not reported (see standalone)")
    # Trap 3: some filings tag a face value of 0 (SUNPHARMA, TITAN): that can't be a share's face value.
    if row.get("face_value") == 0:
        row["face_value"] = math.nan
        receipts.pop("face_value", None)
        notes.append("face_value: tagged 0 -> not reported")
    row["receipts"], row["notes"] = receipts, notes
    return row


# --- listings ----------------------------------------------------------------------------
def _dt(*values) -> datetime | None:
    """First parseable NSE timestamp among values ('-' and blanks occur in old rows)."""
    for v in values:
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
            try:
                return datetime.strptime(str(v).strip(), fmt)
            except ValueError:
                continue
    return None


def parse_integrated_listing(content: bytes) -> pd.DataFrame:
    rows = [{"source": "integrated", "qe": datetime.strptime(r["qe_Date"], "%d-%b-%Y").date(),
             "basis": r["consolidated"], "audited": r["audited"], "revision": r.get("type_Sub"),
             "filed": _dt(r.get("broadcast_Date"), r.get("creation_Date")), "xbrl": r["xbrl"]}
            for r in json.loads(content).get("data", []) if r.get("xbrl")]
    return pd.DataFrame(rows)


def parse_legacy_listing(content: bytes) -> pd.DataFrame:
    rows = [{"source": "legacy", "qe": datetime.strptime(r["toDate"], "%d-%b-%Y").date(),
             "basis": "Consolidated" if r["consolidated"] == "Consolidated" else "Standalone",
             "audited": r["audited"], "revision": r.get("format"),
             "filed": _dt(r.get("filingDate"), r.get("broadCastDate")), "xbrl": r["xbrl"]}
            for r in json.loads(content) if r.get("xbrl") and r.get("period") == "Quarterly"]
    return pd.DataFrame(rows)


def merge_listings(*frames: pd.DataFrame) -> pd.DataFrame:
    """Trap 5: legacy (<= Dec-2024) + integrated (>= Mar-2025) form one quarterly history."""
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True).sort_values(["qe", "filed"]) if frames else pd.DataFrame()


def list_filings(symbol: str, client: http.Client | None = None) -> pd.DataFrame:
    c = client or http.client()
    integrated, page = [], 1
    while True:  # paginated; size=20 overflows within a few years
        r = c.get(IF_API, {"index": "equities", "symbol": symbol, "type": "Integrated Filing- Financials",
                           "page": page, "size": 20}, site="nse", policy="daily").raise_for_status()
        part = parse_integrated_listing(r.content)
        integrated.append(part)
        if len(part) < 20 or page * 20 >= json.loads(r.content).get("totalCount", 0):
            break
        page += 1
    legacy = c.get(LEGACY_API, {"index": "equities", "period": "Quarterly", "symbol": symbol},
                   site="nse", policy="daily").raise_for_status()
    return merge_listings(*integrated, parse_legacy_listing(legacy.content))


def pick_quarters(filings: pd.DataFrame, n: int, basis: str = "Consolidated") -> pd.DataFrame:
    """Latest n quarters; preferred basis first; the latest filing per quarter wins (revisions)."""
    f = filings.assign(_pref=(filings["basis"] != basis).astype(int))
    f = f.sort_values(["qe", "_pref", "filed"], ascending=[False, True, False]).drop_duplicates("qe")
    return f.head(n).drop(columns="_pref").sort_values("qe").reset_index(drop=True)


# --- derived metrics ---------------------------------------------------------------------
def _derived(formula: str, inputs: list[str], note: str | None = None) -> dict:
    d = {"derived": True, "formula": formula, "inputs": inputs}
    return d | ({"note": note} if note else {})


def _consecutive(qes: list[date]) -> bool:
    p = [pd.Period(q, freq="Q") for q in qes]
    return all((b - a).n == 1 for a, b in zip(p, p[1:]))


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """EBITDA, margins, TTM revenue, shares outstanding. Each with a formula receipt."""
    df = df.sort_values("qe").reset_index(drop=True).copy()
    df["receipts"] = [dict(r) for r in df["receipts"]]
    for col in ("ebitda", "ebitda_margin", "pat_margin", "pbt_margin", "ttm_revenue", "shares_outstanding"):
        df[col] = math.nan
    for i, r in df.iterrows():
        rec = df.at[i, "receipts"]
        bank = r["taxonomy"] == "banking"
        if bank:
            rec["ebitda"] = _derived("n/a", [], "EBITDA is not meaningful for banks")
            base, base_name = r["total_income"], "total_income"
        else:
            df.at[i, "ebitda"] = r["pbt"] + r["finance_costs"] + r["dep_amort"] - r["other_income"]
            rec["ebitda"] = _derived("pbt + finance_costs + dep_amort - other_income",
                                     ["pbt", "finance_costs", "dep_amort", "other_income"])
            base, base_name = r["revenue"], "revenue"
            df.at[i, "ebitda_margin"] = df.at[i, "ebitda"] / base
            rec["ebitda_margin"] = _derived("ebitda / revenue", ["ebitda", "revenue"])
        df.at[i, "pat_margin"] = r["pat"] / base
        rec["pat_margin"] = _derived(f"pat / {base_name}", ["pat", base_name])
        df.at[i, "pbt_margin"] = r["pbt"] / base
        rec["pbt_margin"] = _derived(f"pbt / {base_name}", ["pbt", base_name])
        df.at[i, "shares_outstanding"] = r["paid_up_capital"] / r["face_value"]
        rec["shares_outstanding"] = _derived("paid_up_capital / face_value", ["paid_up_capital", "face_value"])
        if i >= 3 and _consecutive(list(df["qe"].iloc[i - 3:i + 1])):
            df.at[i, "ttm_revenue"] = df[base_name].iloc[i - 3:i + 1].sum(min_count=4)
            rec["ttm_revenue"] = _derived(f"sum of last 4 consecutive quarters' {base_name}", [base_name],
                                          "banks: total income" if bank else None)
    return df


def nearest_close(symbol: str, on: date, client: http.Client | None = None,
                  max_back: int = 7) -> tuple[float, date, str] | None:
    """Close on `on` or the nearest earlier trading day: (close, day, source_url)."""
    from .eod import get_eod
    for back in range(max_back + 1):
        d = on - timedelta(days=back)
        eod = get_eod(d, client=client)
        if eod is not None:
            row = eod[(eod["symbol"] == symbol) & (eod["series"] == "EQ")]
            if not row.empty:
                return float(row["close"].iloc[0]), d, eod.attrs["source_url"]
    return None


def add_market_cap(df: pd.DataFrame, symbol: str,
                   close_fn: Callable[[str, date], tuple[float, date, str] | None] = nearest_close) -> pd.DataFrame:
    """market_cap = shares_outstanding x close at quarter-end (nearest earlier trading day)."""
    df = df.copy()
    df["receipts"] = [dict(r) for r in df["receipts"]]
    df["close_at_qe"], df["market_cap"] = math.nan, math.nan
    for i, r in df.iterrows():
        got = close_fn(symbol, r["qe"])
        if got is None:
            continue
        close, day, src = got
        df.at[i, "close_at_qe"] = close
        df.at[i, "market_cap"] = r["shares_outstanding"] * close
        df.at[i, "receipts"]["close_at_qe"] = {"source": src, "date": day.isoformat()}
        df.at[i, "receipts"]["market_cap"] = _derived(
            "shares_outstanding x close_at_qe", ["shares_outstanding", "close_at_qe"],
            f"at quarter-end close ({day.isoformat()})")
    return df


def get_quarterly_financials(symbol: str, n_quarters: int = 12, basis: str = "Consolidated",
                             client: http.Client | None = None) -> pd.DataFrame:
    """One row per quarter-end, oldest first, with receipts + derived metrics. Missing -> NaN, never 0."""
    c = client or http.client()
    picked = pick_quarters(list_filings(symbol, c), n_quarters, basis)
    rows = []
    for _, f in picked.iterrows():
        x = c.get(f["xbrl"], policy="permanent")
        if x.status == 404:      # NSE lists a few XBRL files it no longer serves (LT, Q1 FY26): that quarter is missing
            continue
        row = parse_xbrl(x.raise_for_status().content, f["qe"], f["xbrl"])
        rows.append(row | {"symbol": symbol, "source": f["source"], "filed": f["filed"]})
    return add_derived(pd.DataFrame(rows)) if rows else pd.DataFrame()
