"""Recent official filings for a company page: NSE corporate announcements, tagged by fixed rules.

Every item links its NSE attachment, so a reader can confirm it. Routine paperwork (newspaper copies,
depository certificates, trading-window notices) is left out. Tags come from NSE's own category and
the filing's subject line, never from a model; "worth a look" tags mark events a holder may want to read.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pandas as pd

from finn.data.announcements import get_announcements
from finn.data import http
from finn.data.transcripts import candidates, quarter_for
from finn.ledger.periods import fy_label

DAYS = 90         # filings shown on the page
CALL_DAYS = 372   # announcements read: a year of earnings-call dates for the price chart
# (tag, pattern on "category | subject"), first match wins. Order matters: specific before general.
RULES: list[tuple[str, str]] = [
    ("Auditor change", r"change in auditor|resignation of (the )?(statutory |secretarial )?auditor"),
    ("Pledge", r"\bpledg|encumbrance"),
    ("Regulatory or legal", r"action\(s\) taken or orders passed|\bsebi\b.*\border\b|show cause|penalt|litigation"
                            r"|\bdispute|\bfine\b|\bgst\b.*\bdemand|tax demand|search and seizure|insolvency"),
    ("Resignation", r"cessation|resignation"),
    ("Appointment", r"appointment|change in director|change in management|re-?designation"),
    ("Credit rating", r"credit rating"),
    ("Results", r"financial result|outcome of board meeting.*result|results? for the (quarter|period|year)"),
    ("Earnings call", r"con\.? ?call|conference call|earnings call|analysts?/institutional investor meet"
                      r"|investor presentation|transcript|link of recording"),
    ("Order or contract", r"bagging|receiving.*order|award(ing|ed) of order|order win|letter of award|\bcontract\b"),
    ("Dividend or corporate action", r"dividend|record date|bonus|split|buy-?back|rights issue"),
    ("Board meeting", r"board meeting"),
    ("Expansion", r"commercial production|capacity|acquisition|amalgamation|merger|restructuring|new plant"),
    ("Press release", r"press release"),
]
WORTH_A_LOOK = {"Auditor change", "Pledge", "Regulatory or legal", "Resignation", "Credit rating"}
ROUTINE = re.compile(r"newspaper publication|certificate under sebi|trading window|trading plan"
                     r"|loss of share certificate|duplicate share|investor complaints|compliance certificate"
                     r"|disclosure under sebi takeover", re.I)


def tag(category: str, subject: str) -> str | None:
    """-> a tag, None for routine paperwork, or "Other"."""
    category, subject = (category or "").strip(), (subject or "").strip()
    if ROUTINE.search(category):
        return None
    text = f"{category} | {subject}".lower()
    for name, pat in RULES:
        if re.search(pat, text):
            return name
    return "Other"


def recent(ann: pd.DataFrame, limit: int = 40) -> list[dict]:
    """Newest first; one entry per filing that is not routine paperwork."""
    out = []
    for r in ann.sort_values("filed_at", ascending=False).to_dict("records"):
        t = tag(r.get("category"), r.get("subject"))
        if t is None or not r.get("pdf_url"):
            continue
        filed = r.get("filed_at")
        out.append({"date": filed.date().isoformat() if pd.notna(filed) else None, "tag": t,
                    "worth_a_look": t in WORTH_A_LOOK, "category": (r.get("category") or "").strip(),
                    "subject": " ".join(str(r.get("subject") or "").split())[:280], "pdf_url": r["pdf_url"]})
        if len(out) >= limit:
            break
    return out


def within(ann: pd.DataFrame, end: date, days: int = DAYS) -> pd.DataFrame:
    return ann[ann["filed_at"].notna() & (ann["filed_at"].dt.date > end - timedelta(days=days))]


RECORDING = re.compile(r"recording|audio", re.I)
NOT_EARNINGS = re.compile(r"\bagm\b|annual general meeting|postal ballot|\begm\b", re.I)
RECORDING_WINDOW = 21   # days a transcript may follow its call


def call_dates(ann: pd.DataFrame) -> list[dict]:
    """When each earnings call was held: [{quarter, date, pdf_url}], oldest first.

    SEBI asks for the audio recording within a day of the call, so the date is the last "link of recording"
    filed up to three weeks before the transcript; with no recording, the transcript's own date. A call with a
    recording but no transcript yet still counts. AGM transcripts are not earnings calls."""
    if ann.empty:
        return []
    ann = ann[ann["filed_at"].notna()]
    subj = ann["subject"].fillna("")
    recs = ann[subj.str.contains(RECORDING) & ~subj.str.contains(NOT_EARNINGS)].sort_values("filed_at")
    t = candidates(ann)
    t = t[t["subject"].str.contains("transcript", case=False, na=False) & ~t["subject"].str.contains(NOT_EARNINGS)]
    calls: dict[date, dict] = {}
    for r in t.sort_values("filed_at").to_dict("records"):
        filed = r["filed_at"].date()
        qe = quarter_for(filed)
        if qe in calls:
            continue                                       # a later copy or correction
        near = [d.date() for d in recs["filed_at"] if filed - timedelta(days=RECORDING_WINDOW) <= d.date() <= filed]
        calls[qe] = {"quarter": fy_label(qe), "date": (max(near) if near else filed).isoformat(),
                     "pdf_url": r.get("pdf_url")}
    for r in recs.to_dict("records"):
        qe = quarter_for(r["filed_at"].date())
        calls.setdefault(qe, {"quarter": fy_label(qe), "date": r["filed_at"].date().isoformat(),
                              "pdf_url": r.get("pdf_url")})
    return [calls[q] for q in sorted(calls)]


def get_announcements_for(symbol: str, end: date, client: http.Client | None = None) -> pd.DataFrame:
    return get_announcements(end - timedelta(days=CALL_DAYS), end, [symbol], client=client)
