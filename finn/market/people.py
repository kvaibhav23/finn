"""Who is joining or leaving, read from the company's own NSE filing.

SEBI's Regulation 30 disclosure for a change in directors or key managerial personnel carries a "brief profile
(in case of appointment)". FINN reads that, from the filing itself, rather than scraping LinkedIn (its terms
forbid scraping) or asking a model what it knows about the person.

    page    the first page that mentions a profile (rule)
    excerpt the text after the "brief profile" label, up to the next row of the table (rule)
    card    name, role, effective date and earlier roles, picked out by the cheap model; every field must be
            found verbatim in the page text, or it is dropped (the same guard as promise quotes)

A scanned filing with no text layer gives None and the digest links the PDF.
"""
from __future__ import annotations

import re

import pymupdf
from pydantic import BaseModel, Field

from finn import llm
from finn.data import http
from finn.data.text import canonical, normalise

TAGS = {"Appointment", "Resignation"}
MAX_PER_RUN = 20          # PDFs read per run; each is downloaded once (cached for good)
EXCERPT = 600             # characters of the profile shown
PAGE_CHARS = 6000         # characters of the page given to the model

LABEL = re.compile(r"brief\s+profile(\s*\(in\s+case\s+of\s+appointment\))?|profile\s+of\s+(mr|ms|mrs|dr)\b", re.I)
# The rows that follow the profile in SEBI's format: where the excerpt stops.
TITLE = re.compile(r"\b(Mr|Ms|Mrs|Dr|Prof|Shri|Smt)\.?\s+[A-Z]")
# A full stop that ends a sentence: not the one in "Mr." or "Dr.", and followed by a space or the end.
SENTENCE_END = re.compile(r"(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bMrs)(?<!\bProf)(?<!\bSmt)(?<!\bShri)\.(?=\s|$)")
NEXT_ROW = re.compile(r"\n\s*\d{1,2}\.?\s*\n|disclosure\s+of\s+relationships?|relationship\s+(with|between)", re.I)


class Card(BaseModel):
    found: bool = Field(description="true only if the page describes a named person joining or leaving")
    name: str | None = Field(None, description="the person's name, copied exactly")
    role: str | None = Field(None, description="the position they are joining or leaving, copied exactly")
    effective: str | None = Field(None, description="the date it takes effect, copied exactly")
    previous: list[str] = Field(default_factory=list,
                                description="up to 4 earlier roles or employers, each a phrase copied exactly")


PROMPT = """Below is one page of an Indian listed company's stock-exchange filing about a change in its directors or
senior management. The text came from a PDF, so table columns may be interleaved.

Copy, never paraphrase: every value must appear character for character in the page. Leave a field empty if the
page does not state it. "previous" lists earlier roles or employers of the person (for example "Chairman and
Managing Director of the Cummins Group in India"), at most 4, most senior first.

PAGE:
{page}"""


def profile_page(pdf: bytes) -> tuple[int, str] | None:
    """(1-based page number, normalised text) of the first page with a profile label, or None (no text layer,
    or no profile)."""
    try:
        doc = pymupdf.open(stream=pdf, filetype="pdf")
    except Exception:                                   # noqa: BLE001 - a corrupt attachment is just "no profile"
        return None
    for i, page in enumerate(doc):
        text = normalise(page.get_text())
        if LABEL.search(text):
            return i + 1, text
    return None


def excerpt(text: str) -> str | None:
    """The words after the profile label, up to the next row of the table, cut at a sentence end."""
    m = LABEL.search(text)
    if not m:
        return None
    rest = text[m.end():]
    stop = NEXT_ROW.search(rest, 40)
    body = canonical(rest[:stop.start()] if stop else rest)
    # Scanned tables put other row labels before the profile; profiles open with the person's title.
    who = TITLE.search(body[:250])
    body = re.sub(r"^[\s:.\-–]+", "", body[who.start():] if who else body)
    if len(body) < 40:
        return None
    if len(body) > EXCERPT:
        ends = [m.end() for m in SENTENCE_END.finditer(body[:EXCERPT + 1])]
        body = body[:ends[-1]] if ends and ends[-1] > 200 else body[:EXCERPT].rsplit(" ", 1)[0] + "…"
    return body


def verified(card: Card, text: str) -> dict:
    """Only the fields found verbatim (after typographic normalisation) in the page."""
    page = canonical(text)
    ok = lambda s: bool(s) and canonical(s) in page
    out = {k: canonical(getattr(card, k)) if ok(getattr(card, k)) else None for k in ("name", "role", "effective")}
    out["previous"] = [canonical(p) for p in card.previous[:4] if ok(p)]
    return out


def read_profile(pdf: bytes, symbol: str = "", use_model: bool = True) -> dict | None:
    hit = profile_page(pdf)
    if not hit:
        return None
    page_no, text = hit
    out: dict = {"page": page_no, "excerpt": excerpt(text)}
    if use_model:
        try:
            card = llm.call("profile", PROMPT.format(page=text[:PAGE_CHARS]), Card, symbol=symbol)
            if card.found:
                out |= verified(card, text)
        except llm.LLMError:                            # no key (a local run) or the model failed: the excerpt stands
            pass
    return out if out.get("excerpt") or out.get("name") else None


def add_profiles(symbol: str, filings: list[dict] | None, client: http.Client, days_back: str,
                 use_model: bool = True) -> int:
    """Attach `profile` to recent appointment and resignation filings (in place). Returns PDFs read."""
    n = 0
    for f in filings or []:
        if n >= MAX_PER_RUN:
            break
        if f["tag"] not in TAGS or not f["pdf_url"].lower().endswith(".pdf") or (f.get("date") or "") < days_back:
            continue
        r = client.get(f["pdf_url"], policy="permanent")
        n += 1
        if r.ok and r.content:
            f["profile"] = read_profile(r.content, symbol, use_model)
    return n
