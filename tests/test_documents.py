"""annual reports (trap 9) and transcripts (trap 7, discovery, parsing, verbatim rule)."""
import io
import zipfile
from datetime import date

import pandas as pd

from finn.data import annual_reports as ar
from finn.data import transcripts as tr
from finn.data.announcements import parse_announcements

TCS_FY26_REVENUE = 2_670_210_000_000  # XBRL, 12-month consolidated (Q4 FY26 integrated filing)


def test_ar_listing(fx):
    rows = ar.parse_listing(fx("ar_listing_tcs.json"))
    assert len(rows) == 17 and rows[0]["fy"] == "2025-26" and rows[0]["url"].endswith(".pdf")


def test_trap9_numbers_are_verified_against_text_not_extracted(fx):
    pages = ar.extract_pages(fx("ar_tcs_fy26_excerpt.pdf"))
    assert 5 in ar.find_value_pages(pages, TCS_FY26_REVENUE)   # "2,67,021" on the consolidated P&L page
    first, last = ar.sections(pages)["consolidated_pl"]
    assert first <= 5 <= last
    assert not any(name for name in dir(ar) if "table" in name.lower())  # text-only module, by design


def test_ar_zip_unwrap(fx):
    pdf = fx("ar_tcs_fy26_excerpt.pdf")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("AR.pdf", pdf)
    assert ar.pdf_bytes(buf.getvalue(), "https://x/AR_1.zip") == pdf


def test_trap7_ligatures_normalised_and_quotes_verified(fx):
    p = tr.parse_transcript(fx("transcript_tcs_2026-09.pdf"))
    assert "Chief Financial Officer" in p["text"] and "Ư" not in p["text"]
    assert tr.verify_quote("Mr. Samir Seksaria, Chief Financial Officer.", p["text"])
    assert not tr.verify_quote("Mr. Samir Seksaria, Chief Executive Officer.", p["text"])   # wording must match
    assert not tr.verify_quote("mr. samir seksaria, chief financial officer.", p["text"])   # case must match


def test_parse_chorus_layout(fx):
    p = tr.parse_transcript(fx("transcript_tcs_2026-09.pdf"))
    assert p["layout"] == "chorus" and len(p["turns"]) > 80 and not p["warnings"]
    assert {"K Krithivasan", "Samir Seksaria", "Nehal Shah"} <= set(p["management"])
    assert "Gaurav Rateria" in p["analysts"] and "Nehal Shah" not in p["analysts"]


def test_parse_ril_layout_and_guidance_quotes_are_verbatim(fx):
    p = tr.parse_transcript(fx("transcript_reliance_2026-06.pdf"))
    assert p["layout"] == "ril" and "Manish Adukia" in p["analysts"]
    cands = tr.guidance_candidates(p)
    assert any("$9.9" in c["quote"] for c in cands)
    assert all(tr.verify_quote(c["quote"], p["text"]) for c in cands)


def test_quarter_for():
    assert tr.quarter_for(date(2026, 6, 3)) == date(2026, 3, 31)
    assert tr.quarter_for(date(2026, 10, 14)) == date(2026, 9, 30)
    assert tr.quarter_for(date(2026, 1, 1)) == date(2025, 12, 31)


def test_widened_discovery_finds_asianpaint_mar26_and_excludes_agm(fx):
    ann = parse_announcements(fx("ann_asianpaint_13m.json"))
    cand = tr.candidates(ann)
    q4 = cand[cand["pdf_url"].str.contains("Transcript_Q4FY26")]
    agm = cand[cand["pdf_url"].str.contains("AGMTranscript")]
    assert len(q4) == 1 and len(agm) == 1
    # Confirm by first pages (fixtures hold the real first pages of both PDFs).
    pdfs = {q4["pdf_url"].iloc[0]: fx("transcript_asianpaint_2026-03_p1-3.pdf"),
            agm["pdf_url"].iloc[0]: fx("agm_asianpaint_2026_p1-2.pdf")}
    found = tr.select_transcripts(pd.concat([q4, agm]), pdfs.__getitem__)
    assert list(found["quarter_end"]) == [date(2026, 3, 31)]
    assert "Q4FY26" in found["pdf_url"].iloc[0]


def test_agm_job_title_does_not_exclude_an_earnings_call():
    roster = "Transcript of the Investor Conference, quarter ended 31st March 2026. Mr. Lakshya Sharma : AGM – Finance"
    assert tr.is_earnings_transcript(roster)
    assert not tr.is_earnings_transcript("Transcript of the 80th Annual General Meeting; financial results discussed")
    assert not tr.is_earnings_transcript("Transcript of the 80th AGM; quarter ended June 2026")


def test_con_call_subjects_are_candidates():
    ann = pd.DataFrame([
        {"category": tr.ANALYST_CATEGORY, "subject": "Con. Call recording and transcript", "pdf_url": "a"},
        {"category": tr.ANALYST_CATEGORY, "subject": "Earnings call held on 29 July", "pdf_url": "b"},
        {"category": tr.ANALYST_CATEGORY, "subject": "Schedule of analyst meet", "pdf_url": "c"},
        {"category": "Updates", "subject": "Transcript of conference", "pdf_url": "d"},
    ])
    assert list(tr.candidates(ann)["pdf_url"]) == ["a", "b", "d"]


def test_ir_opened_call_keeps_opening_remarks_and_firm_labelled_analysts(fx):
    """Asian Paints: IR head opens, moderator appears only at Q&A, analysts labelled "Name (Firm):"."""
    p = tr.parse_transcript(fx("transcript_asianpaint_2025-06_excerpt.pdf"))
    assert set(p["management"]) == {"Amit Syngle", "Lakshya Sharma"}
    assert {"Abneesh Roy", "Tejash Shah"} <= set(p["analysts"])     # Tejash's first turn has no "(Firm)" label
    assert tr.opening_remarks(p) == {"first_page": 2, "last_page": 4, "qa_page": 4,
                                     "speakers": ["Lakshya Sharma", "Amit Syngle"]}
    sents = tr.management_sentences(p)
    assert any(s["page"] == 2 and s["speaker"] == "Amit Syngle" for s in sents)    # opening remarks kept
    assert not any("P a g e" in s["sentence"] for s in sents)                     # "3 | P a g e" footer stripped


def test_segment_headings_fold_into_the_speakers_turn(fx):
    """Dixon: "Mobile Phones:" etc. inside prepared remarks are headings, not speakers."""
    p = tr.parse_transcript(fx("transcript_dixon_2025-06_excerpt.pdf"))
    speakers = {t["speaker"] for t in p["turns"]}
    assert not speakers & {"Mobile Phones", "LED TV", "Refrigerators", "Lighting", "At Rexxam Dixon Electronics"}
    assert {"Atul Lall", "Saurabh Gupta"} <= set(p["management"])
    assert "P Khandelwal" in p["analysts"]                          # introduced as "Piyush Khandelwal"
    heading = [s for s in tr.management_sentences(p) if "Mobile Phones:" in s["sentence"]]
    assert heading and heading[0]["speaker"] == "Atul Lall" and heading[0]["page"] == 3


def test_management_sentences_are_verbatim_with_start_page(fx):
    pdf = fx("transcript_dixon_2025-06_excerpt.pdf")
    p = tr.parse_transcript(pdf)
    pages = {}
    for page, line in tr.page_lines(pdf):
        pages[page] = pages.get(page, "") + " " + line
    sents = tr.management_sentences(p)
    assert len(sents) > 20 and all(tr.verify_quote(s["sentence"], p["text"]) for s in sents)
    starts = [s for s in sents if tr.canonical(s["sentence"][:30]) in tr.canonical(pages[s["page"]])]
    assert len(starts) == len(sents)


def test_split_sentences_keeps_abbreviations_and_decimals():
    text = "Mr. Rane said margins of 18.5% will hold. Capex is Rs. 700 crores! Next?"
    assert [s for _, s in tr.split_sentences(text)] == [
        "Mr. Rane said margins of 18.5% will hold.", "Capex is Rs. 700 crores!", "Next?"]
