"""Text normalisation shared by every PDF-derived source.

Trap 7: some PDFs map ligatures to wrong glyphs ('OƯicer' for 'Officer'); without fixing that,
verbatim quotes and keyword search silently fail.
"""
from __future__ import annotations

import re
import unicodedata

GLYPH_FIXES = {"Ư": "ff"}  # TCS transcripts: bad ToUnicode map for the 'ff' ligature
PUNCT = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}


def normalise(s: str) -> str:
    """NFKC (folds ﬁ/ﬂ ligatures) + known broken glyphs. Keeps line breaks."""
    s = unicodedata.normalize("NFKC", s)
    for bad, good in GLYPH_FIXES.items():
        s = s.replace(bad, good)
    return s


def canonical(s: str) -> str:
    """For matching only: normalise + straight quotes/dashes + collapsed whitespace. Case is kept
    (a quote must be verbatim; only typography and line wrapping are forgiven)."""
    s = normalise(s)
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()
