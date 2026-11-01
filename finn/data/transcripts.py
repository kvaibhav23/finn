"""Earnings-call transcripts: discover, confirm, segment into speaker turns, verify quotes (spike 07).

Discovery is widened beyond subjects containing "transcript": candidates also include
con-call / conference-call / earnings-call / investor-conference subjects in the analyst-meet
category, and every candidate is *confirmed by its PDF's first pages* (an earnings transcript,
not an AGM). Asian Paints calls its earnings call an "Investor Conference"; subject-only rules
missed its Mar-26 transcript.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Callable

import pandas as pd
import pymupdf

from . import http
from .announcements import get_announcements
from .text import canonical, normalise

ANALYST_CATEGORY = "Analysts/Institutional Investor Meet/Con. Call Updates"
CANDIDATE_SUBJECT = re.compile(r"transcript|con\.?\s*call|conference\s+call|earnings\s+call|investor\s+conference", re.I)
EARNINGS_MARKER = re.compile(r"earnings|financial\s+results|results\s+for|quarter\s+(and\s+\w+\s+)?ended|"
                             r"financial\s+performance|Q[1-4]\s*'?\s*FY", re.I)
NOT_SPEAKERS = {"isin", "kind attn", "date", "sub", "subject", "scrip code", "symbol", "series", "email",
                "e-mail", "tel", "cin", "website", "note", "disclaimer", "encl", "ref", "management",
                "participants", "scrip id", "security code", "regd. office", "phone"}
SPEAKER_PATTERNS = [  # Reliance's explicit labels first, then the common "Name:" layout
    (re.compile(r"^Questioner\s*\(([^,)]+)(?:,[^)]*)?\)\s*(.*)$"), "analyst", "ril"),
    (re.compile(r"^Company Speaker\s*\(([^)]+)\)\s*(.*)$"), "management", "ril"),
    (re.compile(r"^Sh\.?\s+([A-Z][\w.]*(?:\s+[A-Z][\w.]*){0,3})\s+\d{2}:\d{2}:\d{2}\s*[–-].*?\)\s*(.*)$"), "management", "ril"),
    (re.compile(r"^([A-Z][A-Za-z.'\-]*(?:\s+[A-Z][A-Za-z.'\-]*){0,3})\s*\([^)]{2,40}\)\s*:\s*(.*)$"), "analyst", "chorus"),
    (re.compile(r"^([A-Z][A-Za-z.'\-]*(?:\s+[A-Z][A-Za-z.'\-]*){0,3})\s*:\s*(.*)$"), None, "chorus"),
]  # "Name (Firm):" is how Asian Paints labels an analyst's first turn (no moderator introduction)
QA_START = re.compile(r"first question|question[- ]and[- ]answer|Q\s*&\s*A|begin (the|with) (the )?question|"
                      r"open (the )?(floor|line) for question", re.I)
FORWARD = re.compile(r"\b(we expect|we are expecting|expect(ed)? to|guidance|guide|we will|we aim|aiming|target|"
                     r"going forward|next (year|quarter|fiscal|financial year)|by FY ?'?\d{2}|in FY ?'?\d{2}|"
                     r"outlook|should be able to|confident|anticipate|plan to|on track)\b", re.I)


# --- discovery ---------------------------------------------------------------------------
def quarter_for(filed: date) -> date:
    """Results quarter a transcript belongs to: the latest quarter-end strictly before filing."""
    p = pd.Period(filed, freq="Q")
    qe = p.end_time.date()
    return qe if qe < filed else (p - 1).end_time.date()


def candidates(ann: pd.DataFrame) -> pd.DataFrame:
    subj = ann["subject"].fillna("")
    in_cat = (ann["category"] == ANALYST_CATEGORY) & subj.str.contains(CANDIDATE_SUBJECT)
    anywhere = subj.str.contains("transcript", case=False)
    return ann[in_cat | anywhere]


def first_pages_text(pdf: bytes, n: int = 2) -> str:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return normalise(" ".join(doc[i].get_text() for i in range(min(n, doc.page_count))))


AGM = re.compile(r"annual\s+general\s+meeting|\b\d+(st|nd|rd|th)\s+AGM\b|\bAGM\s+of\s+the\s+company", re.I)


def is_earnings_transcript(first_pages: str) -> bool:
    """Bare 'AGM' is not enough to exclude: it is also a job title ('AGM - Finance' in Asian
    Paints' Q4 FY26 roster = Assistant General Manager)."""
    t = " ".join(first_pages.split())
    return bool(re.search(r"transcript", t, re.I)) and bool(EARNINGS_MARKER.search(t)) and not AGM.search(t)


def select_transcripts(ann: pd.DataFrame, pdf_fn: Callable[[str], bytes]) -> pd.DataFrame:
    """Confirm candidates by PDF first pages; one per results quarter (latest filing wins)."""
    rows = []
    for _, r in candidates(ann).iterrows():
        text = first_pages_text(pdf_fn(r["pdf_url"]))
        if is_earnings_transcript(text):
            filed = r["filed_at"].date()
            rows.append({"symbol": r["symbol"], "quarter_end": quarter_for(filed), "filed_at": r["filed_at"],
                         "pdf_url": r["pdf_url"], "subject": r["subject"], "seq_id": r["seq_id"]})
    out = pd.DataFrame(rows, columns=["symbol", "quarter_end", "filed_at", "pdf_url", "subject", "seq_id"])
    return (out.sort_values("filed_at").drop_duplicates(["symbol", "quarter_end"], keep="last")
               .sort_values("quarter_end").reset_index(drop=True))


def find_transcripts(symbol: str, start: date, end: date, client: http.Client | None = None) -> pd.DataFrame:
    c = client or http.client()
    ann = get_announcements(start, end, [symbol], client=c)
    return select_transcripts(ann, lambda url: c.get(url, policy="permanent").raise_for_status().content)


# --- parsing -----------------------------------------------------------------------------
def page_lines(pdf: bytes) -> list[tuple[int, str]]:
    """(page, line), normalised, with repeated headers/footers and 'Page x of y' removed.
    Only lines in the first/last 4 of a page count as header/footer candidates: 'Moderator:'
    and the CEO's name recur on most pages and must survive."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pages = [[normalise(l).strip() for l in p.get_text().splitlines() if l.strip()] for p in doc]
    freq = Counter(l for p in pages for l in set(p[:4] + p[-4:]))
    repeated = {l for l, c in freq.items() if c >= max(3, len(pages) // 2) and not l.endswith(":")}
    return [(i, l) for i, p in enumerate(pages, 1) for l in p
            if l not in repeated and not re.fullmatch(r"(Page\s*)?\d+(\s*(of|/)\s*\d+)?\s*\|?|\d+\s*\|\s*P\s?a\s?g\s?e", l, re.I)]


def _roster(lines: list[tuple[int, str]]) -> tuple[set[str], set[str]]:
    """Names from the cover roster: "MR. NAME – TITLE" (Chorus Call) or "Mr. Name : Title" (Asian Paints)."""
    text = " ".join(l for _, l in lines[:120])
    def names(block):
        return {re.sub(r"\s+", " ", n).strip().title()
                for n in re.findall(r"\b(?i:MR|MS|MRS|DR)\.?\s+([A-Z][A-Za-z.\s]+?)\s*[–:-]", block)}
    m = re.search(r"(?:MANAGEMENT|Management)\s*:(.{0,800}?)(MODERATOR\s*:|Moderator\s*:|Disclaimer\s*:|$)", text)
    h = re.search(r"MODERATOR\s*:(.*?)(Moderator\s*:|$)", text)
    return (names(m.group(1)) if m else set()), (names(h.group(1)[:300]) if h else set())


def _turns(lines: list[tuple[int, str]], listed: set[str] = frozenset()) -> tuple[list[dict], str | None]:
    """Turns start at the first "Moderator:" line or the first rostered speaker, whichever is first:
    at Asian Paints the IR head opens the call and the moderator only appears at Q&A."""
    listed_lc = {n.lower() for n in listed}
    def opens(l):
        m = SPEAKER_PATTERNS[-1][0].match(l)
        return re.match(r"Moderator\s*:|Transcript\s*:$", l) or (m and m.group(1).strip().lower() in listed_lc)
    start = next((k for k, (_, l) in enumerate(lines) if opens(l)), None)
    if start is None:
        return [], None
    if lines[start][1].lower().startswith("transcript"):
        start += 1
    out, cur, layouts = [], None, Counter()
    for page, l in lines[start:]:
        for pat, role, layout in SPEAKER_PATTERNS:
            m = pat.match(l)
            if m and m.group(1).strip().lower() not in NOT_SPEAKERS:
                cur = {"speaker": m.group(1).strip().rstrip("."), "page": page, "text": m.group(2), "hint": role,
                       "page_marks": [(0, page)]}  # (char offset in text, page): turns can span pages
                out.append(cur)
                layouts[layout] += 1
                break
        else:
            if cur:
                if page != cur["page_marks"][-1][1]:
                    cur["page_marks"].append((len(cur["text"]) + 1, page))
                cur["text"] += " " + l
    return out, ("ril" if layouts["ril"] else "chorus") if out else None


def _rosterish(sp: str, listed: set[str]) -> bool:
    """Same first name or surname as a roster entry ("Saurabh Gpta" typo, "RJ" vs "R.J. Jeyamurugan")."""
    p = sp.lower().split()
    return bool(p) and any(p[0] == n.lower().split()[0] or p[-1] == n.lower().split()[-1] for n in listed)


def _qa_index(turns: list[dict]) -> int:
    """First moderator/host turn after management has spoken that opens Q&A (the moderator's
    opening housekeeping also mentions the Q&A session), else len(turns)."""
    first = next((k for k, t in enumerate(turns) if t["role"] == "management"), len(turns))
    return next((k for k in range(first, len(turns))
                 if turns[k]["role"] in ("moderator", "host") and QA_START.search(turns[k]["text"])), len(turns))


def _label(turns: list[dict], listed: set[str], hosts: set[str]) -> None:
    intro = " ".join(t["text"] for t in turns if t["speaker"].lower() == "moderator")
    windows = " ".join(intro[m.end():m.end() + 100] for m in re.finditer(r"question", intro, re.I))
    listed_lc, hosts_lc = {n.lower() for n in listed}, {n.lower() for n in hosts}

    def introduced(sp):
        """Full name; first-name prefix (or initial) + surname ("P Khandelwal" <- "Piyush Khandelwal");
        or first name + "with/from" ("Girish with Morgan Stanley"). Surname alone is unsafe (Shah)."""
        parts = sp.split()
        if re.search(rf"\b{re.escape(sp)}\b", windows, re.I):
            return True
        if len(parts) < 2:
            return False
        first = parts[0].rstrip(".")
        prefix = first[:3] if len(first) >= 3 else first if len(first) == 1 else None
        return bool(prefix and re.search(rf"\b{re.escape(prefix)}\w*\.?\s+{re.escape(parts[-1])}\b", windows, re.I)
                    or len(first) >= 3 and re.search(rf"\b{re.escape(first)}\s+(with|from|of)\b", windows, re.I))

    labelled = {t["speaker"] for t in turns if t["hint"] == "analyst"}
    # Where analysts carry "(Firm)" labels the roster is the management list, so an unrostered
    # speaker is an analyst even on a turn without the label (Asian Paints Q1 FY26 "Tejash Shah").
    firm_style = bool(listed and labelled) and all(t["hint"] in (None, "analyst") for t in turns)  # not RIL
    analysts = labelled | {sp for sp in {t["speaker"] for t in turns}
                           if sp.lower() != "moderator" and sp.lower() not in listed_lc
                           and (introduced(sp) or firm_style and not _rosterish(sp, listed))}
    for t in turns:
        sp = t["speaker"]
        t["role"] = (t.pop("hint") or ("moderator" if sp.lower() == "moderator" else
                                       "host" if sp.lower() in hosts_lc else
                                       "analyst" if sp in analysts else "management"))


def _fold_headings(turns: list[dict], listed: set[str]) -> list[dict]:
    """Section headings inside prepared remarks ("Mobile Phones:", "Lighting:" at Dixon) parse as
    speakers. Fold a would-be management speaker back into the preceding management turn when it
    is not on the roster (by first name or surname), never named by the moderator/host, and only
    appears before Q&A. Needs a roster; without one nothing is folded."""
    if not listed:
        return turns
    qa = _qa_index(turns)
    said = " ".join(t["text"] for t in turns if t["role"] in ("moderator", "host"))
    where = {}
    for k, t in enumerate(turns):
        where.setdefault(t["speaker"], []).append(k)
    pseudo = {sp for sp, ks in where.items()
              if turns[ks[0]]["role"] == "management" and max(ks) < qa and not _rosterish(sp, listed)
              and not re.search(rf"\b{re.escape(sp)}\b", said, re.I)}
    out = []
    for t in turns:
        if t["speaker"] in pseudo and out and out[-1]["role"] == "management":
            prev, head = out[-1], " " + t["speaker"] + ": "
            base = len(prev["text"]) + len(head)
            for k, (o, p) in enumerate(t["page_marks"]):
                if p != prev["page_marks"][-1][1]:
                    prev["page_marks"].append((len(prev["text"]) + 1 if k == 0 else base + o, p))
            prev["text"] += head + t["text"]
        else:
            out.append(t)
    return out


def parse_transcript(pdf: bytes) -> dict:
    """-> {"turns": [{speaker, role, page, text}], "management", "analysts", "hosts", "layout",
    "text", "warnings"}. Empty turns + a warning if the layout is unknown (never silently skipped)."""
    lines = page_lines(pdf)
    listed, hosts = _roster(lines)
    turns, layout = _turns(lines, listed)
    _label(turns, listed, hosts)
    turns = _fold_headings(turns, listed)
    warnings = [] if turns else ["no speaker turns parsed: unknown transcript layout"]
    return {"turns": turns, "layout": layout, "hosts": sorted(hosts),
            "management": sorted({t["speaker"] for t in turns if t["role"] == "management"}),
            "analysts": sorted({t["speaker"] for t in turns if t["role"] == "analyst"}),
            "text": "\n".join(l for _, l in lines), "warnings": warnings}


def guidance_candidates(parsed: dict) -> list[dict]:
    """Management sentences with forward-looking language and a number. Verbatim, for
    downstream classification; never paraphrased here."""
    out = []
    for t in parsed["turns"]:
        if t["role"] != "management":
            continue
        for s in re.split(r"(?<=[.?!])\s+", t["text"]):
            if FORWARD.search(s) and re.search(r"\d", s) and 60 <= len(s) <= 320:
                out.append({"speaker": t["speaker"], "page": t["page"], "quote": s.strip()})
    return out


# High-recall filter for building the golden set: any forward-looking word, number or not.
FORWARD_BROAD = re.compile(
    r"\b(expect\w*|guid(e|ed|es|ing|ance)|target\w*|aim(s|ed|ing)?|will|won't|\w+'ll|going to|gonna|"
    r"outlook|going forward|next (quarter|year|fiscal|financial year|few (quarters|years|months))|"
    r"coming (quarters?|years?|months)|[12]H|H[12]|by FY ?'?\d{2}|FY ?'?2[6-9]|sustain\w*|range|"
    r"anticipat\w*|plan(s|ned|ning)?|intend\w*|should|would|hope\w*|likely|confident|on track|"
    r"(medium|long|near|short)[- ]term|ahead|trajectory|pipeline|foresee\w*|project(ed|ing|ion)s?)\b", re.I)
ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|Rs|No|Nos|vs|approx|Sr|Jr|St|i\.e|e\.g|Co|Ltd|Pvt|Inc)\.$", re.I)


def split_sentences(text: str) -> list[tuple[int, str]]:
    """-> [(char offset, sentence)]. Splits on .?! + space, but not after Mr./Rs./No. etc.;
    decimals ("4.5") never split because no space follows the point."""
    out, start = [], 0
    for m in re.finditer(r"(?<=[.?!])\s+", text):
        piece = text[start:m.start()]
        if ABBREV.search(piece):
            continue
        if piece.strip():
            out.append((start, piece.strip()))
        start = m.end()
    if text[start:].strip():
        out.append((start, text[start:].strip()))
    return out


def _page_at(marks: list[tuple[int, int]], offset: int) -> int:
    return [p for o, p in marks if o <= offset][-1]


def management_sentences(parsed: dict, pattern: re.Pattern | None = FORWARD_BROAD) -> list[dict]:
    """Every management sentence (matching `pattern`, if given) with the page it starts on.
    Each one is checked verbatim against the transcript text; failures are dropped, never repaired."""
    out = []
    for t in parsed["turns"]:
        if t["role"] != "management":
            continue
        for off, s in split_sentences(t["text"]):
            if (pattern is None or pattern.search(s)) and verify_quote(s, parsed["text"]):
                out.append({"speaker": t["speaker"], "page": _page_at(t.get("page_marks", [(0, t["page"])]), off),
                            "sentence": s})
    return out


def opening_remarks(parsed: dict) -> dict | None:
    """Page span of prepared remarks: first management turn -> the moderator turn that opens Q&A."""
    turns = parsed["turns"]
    first = next((k for k, t in enumerate(turns) if t["role"] == "management"), None)
    if first is None:
        return None
    qa = _qa_index(turns)
    qa = qa if qa < len(turns) else None
    last = turns[qa - 1] if qa else turns[-1]
    end_page = last.get("page_marks", [(0, last["page"])])[-1][1]
    return {"first_page": turns[first]["page"], "last_page": end_page,
            "qa_page": turns[qa]["page"] if qa else None,
            "speakers": list(dict.fromkeys(t["speaker"] for t in turns[first:qa or None] if t["role"] == "management"))}


def verify_quote(quote: str, source_text: str) -> bool:
    """CLAUDE.md rule: a quote is kept only if found verbatim in the source after normalisation
    (ligatures, quotes/dashes, whitespace/line wraps). Case and wording must match exactly."""
    q = canonical(quote)
    return bool(q) and q in canonical(source_text)
