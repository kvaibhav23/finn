"""New-appointee profiles from Reg 30 filings: the rule-based excerpt, and the verbatim guard on the model's card."""
from __future__ import annotations

import pymupdf
import pytest

from finn import llm
from finn.market import people


def test_table_filing_gives_the_profile_row_only(fx):
    p = people.read_profile(fx("reg30_dixon_2026-10_p3.pdf"), use_model=False)
    assert p["page"] == 1
    assert p["excerpt"].startswith("Mr. Prithvi Vachani is currently serving as the Vice President")
    assert p["excerpt"].endswith(".") and not p["excerpt"].endswith("Mr.")       # cut at a sentence, not a title
    assert len(p["excerpt"]) <= people.EXCERPT and "Disclosure" not in p["excerpt"]


def test_scanned_table_skips_the_other_row_labels(fx):
    p = people.read_profile(fx("reg30_kpittech_2026-10_p4.pdf"), use_model=False)
    assert p["excerpt"].startswith("Mr. Anant Talaulicar holds a bachelor's degree")


def test_no_text_layer_gives_none():
    doc = pymupdf.open()
    doc.new_page()
    assert people.read_profile(doc.tobytes(), use_model=False) is None
    assert people.read_profile(b"not a pdf", use_model=False) is None


def test_model_fields_not_in_the_page_are_dropped(fx, monkeypatch):
    card = people.Card(found=True, name="Mr. Anant Talaulicar", role="Chief Executive Officer of KPIT",
                       effective="October 28, 2026",
                       previous=["Chairman and Managing Director of the Cummins Group in India", "CEO of Tata Motors"])
    monkeypatch.setattr(llm, "call", lambda *a, **k: card)
    p = people.read_profile(fx("reg30_kpittech_2026-10_p4.pdf"))
    assert p["name"] == "Mr. Anant Talaulicar" and p["effective"] == "October 28, 2026"
    assert p["role"] is None                                                   # invented: not in the filing
    assert p["previous"] == ["Chairman and Managing Director of the Cummins Group in India"]


def test_without_a_key_the_excerpt_stands(fx, monkeypatch):
    def no_key(*a, **k):
        raise llm.LLMError("GEMINI_API_KEY is not set in .env")
    monkeypatch.setattr(llm, "call", no_key)
    p = people.read_profile(fx("reg30_dixon_2026-10_p3.pdf"))
    assert p["excerpt"] and "name" not in p


class FakeClient:
    def __init__(self, pdf):
        self.pdf, self.urls = pdf, []

    def get(self, url, policy=None):
        self.urls.append(url)
        return type("R", (), {"ok": True, "content": self.pdf})()


def test_add_profiles_reads_only_recent_people_filings(fx):
    f = lambda tag, date, url="https://x/a.pdf": {"tag": tag, "date": date, "pdf_url": url}
    filings = [f("Appointment", "2026-10-30"), f("Results", "2026-10-30"), f("Appointment", "2026-08-01"),
               f("Resignation", "2026-10-12", "https://x/b.zip")]
    c = FakeClient(fx("reg30_dixon_2026-10_p3.pdf"))
    assert people.add_profiles("DIXON", filings, c, "2026-10-04", use_model=False) == 1
    assert filings[0]["profile"]["excerpt"] and "profile" not in filings[1] and "profile" not in filings[2]


def test_a_blank_profile_row_is_not_a_profile():
    assert people.excerpt("Brief profile (in case of appointment)\n; Not Applicable Disclosure of relationships "
                          "between directors (in case of appointment of a director). Not Applicable") is None
