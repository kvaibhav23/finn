"""Spike 06: find + download annual reports for any NSE ticker; extract usable text.

Listing: /api/annual-reports?index=equities&symbol=X  (PDF from FY25, ZIP before)
Extraction: pymupdf (whole doc) vs pdfplumber (sampled pages); tables on the P&L page;
scanned-page detection; locate MD&A; cross-check one XBRL number in the text.
"""
import io
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pdfplumber
import pymupdf
from lxml import etree

from common import fetch, log_summary, make_session
from tickers import SAMPLE

API = "https://www.nseindia.com/api/annual-reports"
DOWNLOAD = [("TCS", "2025"), ("DIXON", "2025"), ("DIXON", "2023"), ("KPITTECH", "zip")]  # (symbol, fromYr | "zip" = newest ZIP)
TCS_FY26_XBRL = "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1648408_09042026114218_WEB.xml"
LOW_TEXT = 100            # chars; below this a page is image-only / design / scanned
PLUMBER_SAMPLE = 25       # pages timed with pdfplumber


def list_reports(symbol: str) -> list[dict]:
    f = fetch(make_session("nse"), API, params={"index": "equities", "symbol": symbol})
    if not f.ok:
        print(f"  {symbol}: listing FAIL {f.status}")
        return []
    return f.json().get("data", [])


def pdf_bytes(content: bytes, url: str) -> tuple[bytes, str]:
    if url.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names = z.namelist()
            pdfs = sorted((n for n in names if n.lower().endswith(".pdf")), key=lambda n: -z.getinfo(n).file_size)
            print(f"    zip members: {len(names)} ({len(pdfs)} pdf) -> using {pdfs[0] if pdfs else None}")
            return z.read(pdfs[0]), pdfs[0]
    return content, url.rsplit("/", 1)[-1]


def fy_revenue_from_xbrl() -> float | None:
    f = fetch(make_session("plain"), TCS_FY26_XBRL)
    root = etree.fromstring(f.content)
    X = "{http://www.xbrl.org/2003/instance}"
    fy = {c.get("id") for c in root.iter(f"{X}context")
          if c.findtext(f"{X}period/{X}startDate") == "2025-04-01" and c.findtext(f"{X}period/{X}endDate") == "2026-03-31"
          and not any(m.tag.endswith("explicitMember") for m in c.iter())}
    for el in root:
        if isinstance(el.tag, str) and etree.QName(el).localname == "RevenueFromOperations" and el.get("contextRef") in fy:
            return float(el.text)
    return None


def analyse(symbol: str, data: bytes, name: str, xbrl_check: float | None):
    t0 = time.monotonic()
    doc = pymupdf.open(stream=data, filetype="pdf")
    texts = [p.get_text() for p in doc]
    t_mu = time.monotonic() - t0
    chars = [len(t.strip()) for t in texts]
    low = [i + 1 for i, c in enumerate(chars) if c < LOW_TEXT]
    print(f"    pymupdf: {doc.page_count} pages in {t_mu:.1f}s ({t_mu / doc.page_count * 1000:.0f} ms/page), "
          f"{sum(chars):,} chars, median {sorted(chars)[len(chars) // 2]:,}/page")
    print(f"    low-text pages (<{LOW_TEXT} chars): {len(low)} -> {low[:15]}{' ...' if len(low) > 15 else ''}")
    imgs_on_low = sum(1 for i in low if doc[i - 1].get_images())
    print(f"      of which contain images: {imgs_on_low}")

    def find(pattern):
        return [i + 1 for i, t in enumerate(texts) if re.search(pattern, t, re.I)]
    mdna = find(r"management\s+discussion\s+(and|&)\s+analysis")
    pl = find(r"consolidated\s+statement\s+of\s+profit\s+and\s+loss")
    print(f"    'Management Discussion and Analysis' on pages: {mdna[:12]}")
    print(f"    'Consolidated Statement of Profit and Loss' on pages: {pl[:12]}")

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        n = min(PLUMBER_SAMPLE, len(pdf.pages))
        t0 = time.monotonic()
        pl_chars = sum(len((pdf.pages[i].extract_text() or "").strip()) for i in range(n))
        t_pl = time.monotonic() - t0
        mu_chars = sum(chars[:n])
        print(f"    pdfplumber: first {n} pages in {t_pl:.1f}s ({t_pl / n * 1000:.0f} ms/page) "
              f"-> {pl_chars:,} chars vs pymupdf {mu_chars:,} on same pages; "
              f"est. full doc {t_pl / n * doc.page_count:.0f}s")

        # Tables on the statement page: pick the P&L page that actually has 'Revenue from operations'.
        target = next((p for p in pl if re.search(r"revenue\s+from\s+operations", texts[p - 1], re.I)), None)
        if target:
            mu_tables = doc[target - 1].find_tables().tables
            plb_tables = pdf.pages[target - 1].extract_tables()
            def rev_row(rows):
                for row in rows:
                    cells = [str(c or "") for c in row]
                    if any(re.search(r"revenue\s+from\s+operations", c, re.I) for c in cells):
                        return cells
                return None
            mu_row = next((r for t in mu_tables if (r := rev_row(t.extract()))), None)
            plb_row = next((r for t in plb_tables if (r := rev_row(t))), None)
            print(f"    tables on P&L page {target}: pymupdf {len(mu_tables)} (revenue row: {mu_row}), "
                  f"pdfplumber {len(plb_tables)} (revenue row: {plb_row})")
            line = next((l for l in texts[target - 1].splitlines() if re.search(r"revenue\s+from\s+operations", l, re.I)), "")
            print(f"    plain-text line: {line.strip()[:100]!r}")
        else:
            print("    no P&L page containing 'Revenue from operations' found")

    if xbrl_check:
        full = "\n".join(texts)
        cr = f"{xbrl_check / 1e7:.0f}"
        variants = {f"{xbrl_check / 1e7:,.0f}", re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", cr[:-3]) + "," + cr[-3:]}
        hits = {v: find(re.escape(v))[:6] for v in variants}
        print(f"    XBRL FY26 consolidated revenue {xbrl_check:,.0f} INR = {cr} cr; text hits by page: {hits}")


def main():
    print("== listings ==")
    listings = {}
    for sym in SAMPLE:
        rows = list_reports(sym)
        listings[sym] = rows
        if rows:
            exts = [r["fileName"].rsplit(".", 1)[-1].lower() for r in rows]
            print(f"  {sym}: {len(rows)} reports, FY{rows[-1]['fromYr']}-{rows[-1]['toYr']} .. "
                  f"FY{rows[0]['fromYr']}-{rows[0]['toYr']}; latest filed {rows[0]['broadcast_dttm']} "
                  f"({rows[0]['attFileSize']}); formats {dict((e, exts.count(e)) for e in set(exts))}")

    xbrl_rev = fy_revenue_from_xbrl()

    print("\n== download + extract ==")
    for sym, yr in DOWNLOAD:
        row = next((r for r in listings.get(sym, []) if r["fromYr"] == yr
                    or (yr == "zip" and r["fileName"].lower().endswith(".zip"))), None)
        if not row:
            print(f"  {sym} FY{yr}: not listed")
            continue
        print(f"  {sym} FY{row['fromYr']}-{row['toYr']}: {row['fileName'].rsplit('/', 1)[-1]}")
        f = fetch(make_session("plain"), row["fileName"])
        if not f.ok:
            print(f"    download FAIL {f.status} {f.error}")
            continue
        print(f"    {len(f.content) / 1e6:.1f} MB, latency {f.latency_ms} ms, cached={f.cached}")
        data, name = pdf_bytes(f.content, row["fileName"])
        analyse(sym, data, name, xbrl_rev if (sym, yr) == ("TCS", "2025") else None)

    print("\n" + log_summary())


if __name__ == "__main__":
    main()
