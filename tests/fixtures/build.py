"""Rebuild tests/fixtures/ from the local download cache (data/raw). Never touches the network.

    python tests/fixtures/build.py

Each fixture is a copy, or a trimmed copy, of a cached NSE response; the source URL is listed
below. Large files are trimmed (sample symbols only, or a few PDF pages) to keep the repo small.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
RAW = HERE.parents[1] / "data" / "raw"
SAMPLE = {"RELIANCE", "TCS", "HDFCBANK", "ASIANPAINT", "DIXON", "KPITTECH"}
ARCH = "https://nsearchives.nseindia.com"
API = "https://www.nseindia.com/api"

COPY = {  # fixture name -> cached URL
    "ann_reliance_2026-10.json": f"{API}/corporate-announcements?index=equities&symbol=RELIANCE&from_date=01-10-2026&to_date=31-10-2026",
    "ann_asianpaint_13m.json": f"{API}/corporate-announcements?index=equities&symbol=ASIANPAINT&from_date=01-10-2025&to_date=31-10-2026",
    "listing_tcs_integrated.json": f"{API}/integrated-filing-results?index=equities&symbol=TCS&type=Integrated+Filing-+Financials&page=1&size=20",
    "listing_tcs_legacy.json": f"{API}/corporates-financial-results?index=equities&period=Quarterly&symbol=TCS",
    "ar_listing_tcs.json": f"{API}/annual-reports?index=equities&symbol=TCS",
    "ca_hdfcbank.json": f"{API}/corporates-corporateActions?index=equities&symbol=HDFCBANK",
    "ca_reliance.json": f"{API}/corporates-corporateActions?index=equities&symbol=RELIANCE",
    "ca_dixon.json": f"{API}/corporates-corporateActions?index=equities&symbol=DIXON",
    "xbrl_tcs_2026-09_cons.xml": f"{ARCH}/corporate/xbrl/INTEGRATED_FILING_INDAS_1734607_08102026100810_WEB.xml",
    "xbrl_tcs_2026-06_cons.xml": f"{ARCH}/corporate/xbrl/INTEGRATED_FILING_INDAS_1690004_09072026063620_WEB.xml",
    "xbrl_tcs_2026-03_cons.xml": f"{ARCH}/corporate/xbrl/INTEGRATED_FILING_INDAS_1648408_09042026114218_WEB.xml",
    "xbrl_tcs_2025-12_cons.xml": f"{ARCH}/corporate/xbrl/INTEGRATED_FILING_INDAS_1599094_12012026064316_WEB.xml",
    "xbrl_tcs_2024-12_legacy.xml": f"{ARCH}/corporate/xbrl/INDAS_117182_1341298_09012025093940.xml",
    "xbrl_hdfcbank_2026-09_cons.xml": f"{ARCH}/corporate/xbrl/INTEGRATED_FILING_BANKING_1740913_17102026054812_WEB.xml",
    "xbrl_hdfcbank_2024-12_legacy.xml": f"{ARCH}/corporate/xbrl/BANKING_117525_1359016_23012025122721.xml",
    # Q2 FY26 standalone: management said "18.5%" PBDIT margin -> matches the definition without other income
    "xbrl_asianpaint_2025-09_standalone.xml": f"{ARCH}/corporate/xbrl/INTEGRATED_FILING_INDAS_1572845_12112025080926_WEB.xml",
    "transcript_tcs_2026-09.pdf": f"{ARCH}/corporate/TCS_CORPCS_14102026155941_SEInt14102026_signed.pdf",
    "transcript_reliance_2026-06.pdf": f"{ARCH}/corporate/kavinavora_19072026180618_SE_Transcript.pdf",
}
PDF_PAGES = {  # fixture name -> (cached URL, 0-based pages to keep)
    "transcript_asianpaint_2026-03_p1-3.pdf": (f"{ARCH}/corporate/ASIANPAINT_03062026154629_Reg30_Transcript_Q4FY26.pdf", [0, 1, 2]),
    "agm_asianpaint_2026_p1-2.pdf": (f"{ARCH}/corporate/ASIANPAINT_16072026204353_SEIntimation80thAGMTranscriptandVideosigned.pdf", [0, 1]),
    "ar_tcs_fy26_excerpt.pdf": (f"{ARCH}/annual_reports/AR_29263_TCS_2025_2026_A_17427580_15052026234830.pdf",
                                [0, 3, 41, 42, 167]),  # cover, TOC, MD&A x2, consolidated P&L (p.168)
    # IR head opens (no moderator until Q&A), "Mr. Name : Title" roster, "Name (Firm):" analysts
    "transcript_asianpaint_2025-06_excerpt.pdf": (f"{ARCH}/corporate/ASIANPAINT_02082025122344_SEintimationtranscript.pdf",
                                                  [1, 2, 3, 18, 19, 20]),
    # segment headings in prepared remarks ("Mobile Phones:"), "P Khandelwal" <- "Piyush Khandelwal"
    "transcript_dixon_2025-06_excerpt.pdf": (f"{ARCH}/corporate/DIXON_28072025185656_28072025Transcript.pdf",
                                             [1, 2, 3, 4, 5, 6, 10, 11]),
}


def cached(url: str) -> bytes:
    meta = json.loads((RAW / f"{hashlib.sha256(url.encode()).hexdigest()[:20]}.meta.json").read_text())
    return (RAW / meta["file"]).read_bytes()


def main():
    for name, url in COPY.items():
        (HERE / name).write_bytes(cached(url))

    eq = cached(f"{ARCH}/content/equities/EQUITY_L.csv").decode().splitlines()
    keep = [eq[0]] + [l for l in eq[1:] if l.split(",")[0] in SAMPLE] + eq[1:21]
    (HERE / "equity_l_sample.csv").write_text("\n".join(dict.fromkeys(keep)) + "\n")

    with zipfile.ZipFile(io.BytesIO(cached(f"{ARCH}/content/cm/BhavCopy_NSE_CM_0_0_0_20261030_F_0000.csv.zip"))) as z:
        name = z.namelist()[0]
        lines = z.read(name).decode().splitlines()
    tck = lines[0].split(",").index("TckrSymb")
    rows = [lines[0]] + [l for l in lines[1:] if l.split(",")[tck] in SAMPLE]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, "\n".join(rows) + "\n")
    (HERE / "bhav_udiff_2026-10-30_sample.zip").write_bytes(buf.getvalue())

    full = cached(f"{ARCH}/products/content/sec_bhavdata_full_30102026.csv").decode().splitlines()
    (HERE / "bhav_full_2026-10-30_sample.csv").write_text(
        "\n".join([full[0]] + [l for l in full[1:] if l.split(",")[0].strip() in SAMPLE]) + "\n")

    for name, (url, pages) in PDF_PAGES.items():
        src = pymupdf.open(stream=cached(url), filetype="pdf")
        out = pymupdf.open()
        for p in pages:
            out.insert_pdf(src, from_page=p, to_page=p)
        out.save(HERE / name, garbage=4, deflate=True)

    total = sum(p.stat().st_size for p in HERE.iterdir() if p.suffix != ".py")
    print(f"fixtures: {sum(1 for p in HERE.iterdir() if p.suffix != '.py')} files, {total / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
