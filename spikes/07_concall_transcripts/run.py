"""Spike 07: discover, download and segment earnings-call transcripts (promise-ledger input).

Discovery: NSE announcements (spike 02 endpoint), 13-month window per symbol, subject contains
"transcript". Then, per symbol's latest earnings-call transcript:
  - text via pymupdf, normalised (NFKC + a known broken-ligature glyph), headers/footers removed
  - speaker turns: "Name:" at line start, starting at the first "Moderator:"
  - roles: Moderator / Analyst (introduced as "question is from ... <Name>") / Management (rest,
    cross-checked against the transcript's own MANAGEMENT: roster when present)
  - forward-looking management sentences that contain a number, quoted verbatim with page number
No LLM anywhere; nothing is inferred from the quotes.
"""
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf

from common import fetch, log_summary, make_session
from tickers import SAMPLE

ANN_API = "https://www.nseindia.com/api/corporate-announcements"
FROM, TO = "01-10-2025", "31-10-2026"
QUARTER_ENDS = [date(2025, 9, 30), date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30)]
NOT_SPEAKERS = {"isin", "kind attn", "date", "sub", "subject", "scrip code", "symbol", "series", "email",
                "e-mail", "tel", "cin", "website", "note", "disclaimer", "encl", "ref", "management",
                "moderator s", "participants", "scrip id", "security code", "regd. office", "phone"}
FORWARD = re.compile(r"\b(we expect|we are expecting|expect(ed)? to|guidance|guide|we will|we aim|aiming|target|"
                     r"going forward|next (year|quarter|fiscal|financial year)|by FY ?'?\d{2}|in FY ?'?\d{2}|"
                     r"outlook|should be able to|confident|anticipate|plan to|on track)\b", re.I)


def quarter_for(filed: date) -> date:
    return max(q for q in QUARTER_ENDS + [date(2025, 6, 30)] if q < filed)


def kind_of(subject: str) -> str:
    if re.search(r"annual general meeting|\bAGM\b", subject, re.I):
        return "agm"
    if re.search(r"analyst|investor (meet|day)|conference(?! call)", subject, re.I) and \
            not re.search(r"earning|result|quarter", subject, re.I):
        return "other"
    return "earnings"   # incl. generic "informed the Exchange about Transcript" (checked in the body)


def discover(symbol: str) -> list[dict]:
    f = fetch(make_session("nse"), ANN_API, params={"index": "equities", "symbol": symbol,
                                                    "from_date": FROM, "to_date": TO})
    if not f.ok:
        print(f"  {symbol}: announcements FAIL {f.status}")
        return []
    rows = f.json()
    hits = [r for r in rows if re.search(r"transcript", r.get("attchmntText") or "", re.I)]
    for r in hits:
        r["_filed"] = datetime.strptime(r["an_dt"], "%d-%b-%Y %H:%M:%S").date()
        r["_qe"] = quarter_for(r["_filed"])
        r["_kind"] = kind_of(r["attchmntText"])
    print(f"  {symbol}: {len(rows)} announcements, {len(hits)} transcript filings "
          f"(kinds={dict(Counter(h['_kind'] for h in hits))}, categories={dict(Counter(h['desc'] for h in hits))})")
    return hits


def normalise(s: str) -> str:
    return unicodedata.normalize("NFKC", s).replace("Ư", "ff")  # 'OƯicer' -> 'Officer' (bad ToUnicode map)


def page_lines(doc) -> list[tuple[int, str]]:
    """(page_no, line) with repeated headers/footers and 'Page x of y' removed."""
    pages = [[normalise(l).strip() for l in p.get_text().splitlines() if l.strip()] for p in doc]
    # Header/footer = repeats in the first/last 4 lines of pages. (Whole-page frequency would
    # also delete 'Moderator:' and the CEO's name, which recur on most pages.)
    freq = Counter(l for p in pages for l in set(p[:4] + p[-4:]))
    repeated = {l for l, c in freq.items() if c >= max(3, len(pages) // 2) and not l.endswith(":")}
    out = []
    for i, p in enumerate(pages, 1):
        for l in p:
            if l in repeated or re.fullmatch(r"(Page\s*)?\d+(\s*(of|/)\s*\d+)?\s*\|?", l, re.I):
                continue
            out.append((i, l))
    return out


def roster(lines: list[tuple[int, str]]) -> tuple[set[str], set[str]]:
    """(management, hosts) listed in the transcript header (Chorus-Call style), if any."""
    text = " ".join(l for _, l in lines[:120])
    def names(block):
        return {re.sub(r"\s+", " ", n).strip().title()
                for n in re.findall(r"\b(?:MR|MS|MRS|DR)\.?\s+([A-Z][A-Z.\s]+?)\s*[–-]", block)}
    m = re.search(r"MANAGEMENT\s*:(.*?)(MODERATOR\s*:|Moderator\s*:)", text)
    h = re.search(r"MODERATOR\s*:(.*?)(Moderator\s*:|$)", text)
    return (names(m.group(1)) if m else set()), (names(h.group(1)[:300]) if h else set())


# Speaker-line formats seen: "Name: text" (Chorus Call / most), and Reliance's explicit
# "Questioner (Name, Firm)", "Company Speaker (Name)", "Sh Name 00:00:01 – 00:09:45 (Segment)".
SPEAKER_PATTERNS = [
    (re.compile(r"^Questioner\s*\(([^,)]+)(?:,[^)]*)?\)\s*(.*)$"), "analyst"),
    (re.compile(r"^Company Speaker\s*\(([^)]+)\)\s*(.*)$"), "management"),
    (re.compile(r"^Sh\.?\s+([A-Z][\w.]*(?:\s+[A-Z][\w.]*){0,3})\s+\d{2}:\d{2}:\d{2}\s*[–-].*?\)\s*(.*)$"), "management"),
    (re.compile(r"^([A-Z][A-Za-z.'\-]*(?:\s+[A-Z][A-Za-z.'\-]*){0,3})\s*:\s*(.*)$"), None),
]


def turns(lines: list[tuple[int, str]]) -> list[dict]:
    start = next((k for k, (_, l) in enumerate(lines)
                  if re.match(r"Moderator\s*:|Transcript\s*:$", l)), None)
    if start is None:
        return []
    if lines[start][1].lower().startswith("transcript"):
        start += 1  # Reliance: "Transcript:" marker line, speakers follow
    out, cur = [], None
    for page, l in lines[start:]:
        for pat, role in SPEAKER_PATTERNS:
            m = pat.match(l)
            if m and m.group(1).strip().lower() not in NOT_SPEAKERS:
                cur = {"speaker": m.group(1).strip().rstrip("."), "page": page, "text": m.group(2), "hint": role}
                out.append(cur)
                break
        else:
            if cur:
                cur["text"] += " " + l
    return out


def label_roles(ts: list[dict], listed: set[str], hosts: set[str]) -> tuple[set, set]:
    # Analyst = named by the moderator shortly after the word "question"
    # ("next question is from the line of X", "we have a question from X", "next in line ... question").
    intro = " ".join(t["text"] for t in ts if t["speaker"].lower() == "moderator")
    windows = " ".join(intro[m.end():m.end() + 100] for m in re.finditer(r"question", intro, re.I))
    listed_lc = {n.lower() for n in listed}
    def introduced(sp):  # full name, else first-name prefix + surname ("Jay Doshi" -> "Jaykumar Doshi";
        parts = sp.split()  # surname alone is unsafe: IR head "Nehal Shah" vs analyst "Sandeep Shah")
        if re.search(rf"\b{re.escape(sp)}\b", windows, re.I):
            return True
        return len(parts) > 1 and len(parts[0]) >= 3 and bool(
            re.search(rf"\b{re.escape(parts[0][:3])}\w*\s+{re.escape(parts[-1])}\b", windows, re.I))
    analysts = {sp for sp in {t["speaker"] for t in ts}
                if sp.lower() != "moderator" and sp.lower() not in listed_lc and introduced(sp)}
    hosts_lc = {n.lower() for n in hosts}
    for t in ts:
        sp = t["speaker"]
        t["role"] = (t["hint"] if t.get("hint") else
                     "moderator" if sp.lower() == "moderator" else
                     "host" if sp.lower() in hosts_lc else
                     "analyst" if sp in analysts else "management")
    analysts |= {t["speaker"] for t in ts if t["role"] == "analyst"}
    mgmt = {t["speaker"] for t in ts if t["role"] == "management"}
    return analysts, mgmt


def forward_quotes(ts: list[dict], n: int = 3) -> list[tuple[int, str, str]]:
    out = []
    for t in ts:
        if t["role"] != "management":
            continue
        for s in re.split(r"(?<=[.?!])\s+", t["text"]):
            if FORWARD.search(s) and re.search(r"\d", s) and 60 <= len(s) <= 320:
                out.append((t["page"], t["speaker"], s.strip()))
    return out[:n]


def main():
    print("== discovery ==")
    found = {sym: discover(sym) for sym in SAMPLE}

    print("\n== earnings-transcript coverage by results quarter ==")
    for sym, hits in found.items():
        by_q = Counter(h["_qe"] for h in hits if h["_kind"] == "earnings")
        print(f"  {sym:10} " + " ".join(f"{q:%b%y}:{by_q.get(q, 0)}" for q in QUARTER_ENDS))
    for sym, hits in found.items():
        for h in hits:
            if h["_kind"] != "earnings":
                print(f"  excluded ({h['_kind']}): {sym} {h['an_dt']} {h['attchmntText'][:90]}")

    print("\n== latest earnings transcript per symbol ==")
    summary = []
    for sym, hits in found.items():
        earn = [h for h in hits if h["_kind"] == "earnings"]
        if not earn:
            continue
        h = max(earn, key=lambda r: r["_filed"])
        f = fetch(make_session("plain"), h["attchmntFile"])
        if not f.ok:
            print(f"  {sym}: download FAIL {f.status}")
            continue
        doc = pymupdf.open(stream=f.content, filetype="pdf")
        raw = "".join(p.get_text() for p in doc)
        lines = page_lines(doc)
        listed, hosts = roster(lines)
        ts = turns(lines)
        analysts, mgmt = label_roles(ts, listed, hosts)
        roles = Counter(t["role"] for t in ts)
        words = Counter()
        for t in ts:
            words[t["role"]] += len(t["text"].split())
        unmatched_roster = {n for n in listed if not any(n.lower() == s.lower() for s in mgmt)}
        print(f"\n  --- {sym} filed {h['an_dt']} (quarter {h['_qe']:%b%y}) {len(f.content)/1024:,.0f} KB, "
              f"{doc.page_count} pages, {len(raw):,} chars, low-text pages "
              f"{sum(1 for p in doc if len(p.get_text().strip()) < 100)}")
        print(f"      broken-ligature glyphs fixed: {raw.count(chr(0x01AF))}, NFKC-changed ligatures: "
              f"{sum(raw.count(c) for c in 'ﬀﬁﬂﬃﬄ')}")
        print(f"      turns={len(ts)} {dict(roles)} words={dict(words)}")
        print(f"      management={sorted(mgmt)}")
        print(f"      analysts ({len(analysts)})={sorted(analysts)[:8]}{' ...' if len(analysts) > 8 else ''}")
        print(f"      hosts (MODERATOR: block)={sorted(hosts) or '-'}")
        print(f"      roster (MANAGEMENT: block)={sorted(listed) or 'none in transcript'}; "
              f"roster names not seen as management speakers={sorted(unmatched_roster) or '-'}")
        for t in ts[:6]:
            print(f"      [{t['role'][:4]}] p{t['page']} {t['speaker']}: {t['text'][:90]}")
        print("      forward-looking management quotes (verbatim):")
        for page, sp, s in forward_quotes(ts):
            print(f"        p{page} {sp}: \"{s}\"")
        summary.append({"symbol": sym, "pages": doc.page_count, "turns": len(ts), **roles,
                        "analysts": len(analysts), "mgmt": len(mgmt), "roster": len(listed)})

    print("\n== summary ==")
    for s in summary:
        print(f"  {s}")
    print("\n" + log_summary())


if __name__ == "__main__":
    main()
