"""Annual reports: discover, download (PDF or ZIP), extract normalised page text (spike 06).

Trap 9: PDF tables are layout-dependent, so this module returns *text only*. Numbers come
from XBRL; find_value_pages() exists only to verify that an XBRL number appears in the report.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime

import pymupdf

from . import http
from .text import normalise

API = "https://www.nseindia.com/api/annual-reports"
SECTION_PATTERNS = {
    "mdna": r"management\s+discussion\s+(and|&)\s+analysis",
    "consolidated_pl": r"consolidated\s+statement\s+of\s+profit\s+and\s+loss",
    "standalone_pl": r"(standalone\s+)?statement\s+of\s+profit\s+and\s+loss(?!.*consolidated)",
    "risk": r"\brisk\s+management\b",
    "chairman": r"chairman'?s\s+(message|letter)",
}
TOC_PAGES = 6  # hits in the first pages are usually the table of contents


def parse_listing(content: bytes) -> list[dict]:
    out = []
    for r in json.loads(content).get("data", []):
        filed = r.get("broadcast_dttm")
        out.append({"fy": f"{r['fromYr']}-{str(r['toYr'])[-2:]}", "from_year": int(r["fromYr"]),
                    "url": r["fileName"], "size": r.get("attFileSize"),
                    "filed_at": datetime.strptime(filed, "%d-%b-%Y %H:%M:%S") if filed and filed != "-" else None})
    return out


def list_annual_reports(symbol: str, client: http.Client | None = None) -> list[dict]:
    c = client or http.client()
    r = c.get(API, {"index": "equities", "symbol": symbol}, site="nse", policy="daily").raise_for_status()
    return parse_listing(r.content)


def pdf_bytes(content: bytes, url: str) -> bytes:
    """Older reports come as ZIPs; use the largest PDF inside."""
    if url.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            pdfs = sorted((n for n in z.namelist() if n.lower().endswith(".pdf")), key=lambda n: -z.getinfo(n).file_size)
            if not pdfs:
                raise ValueError(f"no PDF inside {url}")
            return z.read(pdfs[0])
    return content


def extract_pages(pdf: bytes) -> list[str]:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return [normalise(p.get_text()) for p in doc]


def sections(pages: list[str]) -> dict[str, tuple[int, int] | None]:
    """1-based (first, last) page range per section, from running headers; TOC pages ignored."""
    out = {}
    for name, pat in SECTION_PATTERNS.items():
        hits = [i + 1 for i, t in enumerate(pages) if re.search(pat, t, re.I)]
        body = [h for h in hits if h > TOC_PAGES] or hits
        out[name] = (min(body), max(body)) if body else None
    return out


def find_value_pages(pages: list[str], inr_value: float) -> list[int]:
    """Pages containing an XBRL INR value written in crore (western 267,021 or Indian 2,67,021).
    Verification only; never a source of numbers."""
    n = f"{inr_value / 1e7:.0f}"
    western = f"{int(n):,}"
    indian = (re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", n[:-3]) + "," + n[-3:]) if len(n) > 3 else n
    return [i + 1 for i, t in enumerate(pages) if western in t or indian in t]


def get_annual_report(symbol: str, from_year: int, client: http.Client | None = None) -> dict:
    """-> {"symbol", "fy", "url", "filed_at", "pages", "sections"}. LookupError if not listed."""
    c = client or http.client()
    row = next((r for r in list_annual_reports(symbol, c) if r["from_year"] == from_year), None)
    if row is None:
        raise LookupError(f"{symbol}: no annual report for FY{from_year}")
    raw = c.get(row["url"], policy="permanent").raise_for_status().content
    pages = extract_pages(pdf_bytes(raw, row["url"]))
    return {"symbol": symbol, "fy": row["fy"], "url": row["url"], "filed_at": row["filed_at"],
            "pages": pages, "sections": sections(pages)}
