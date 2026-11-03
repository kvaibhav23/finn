// Sentences built by code from facts in the data files, in the reader's language. A sentence whose facts are
// missing is left out rather than worded around the gap; every number shown is one of the facts.

import { dayMonthYear, quarter, rupees, signedPct } from "./format.ts";
import type { Dict } from "./i18n/en.ts";
import type { Lang } from "./i18n/languages.ts";
import type { Market, MoveFacts, Signal } from "./types.ts";

const pct = (n: number) => `${Math.abs(n).toFixed(1)}%`;

export function summary(t: Dict, lang: Lang, symbol: string, m: Market, counts: Record<string, number> | null): string[] {
  const out: string[] = [];
  const p = m.price;
  if (p) {
    let line = t.summary.closed(symbol, rupees(p.close), dayMonthYear(p.as_of, lang));
    if (p.return_1y != null) {
      line += t.summary.year(p.return_1y >= 0, pct(p.return_1y));
      if (p.nifty_return_1y != null) line += t.summary.nifty(p.nifty_return_1y >= 0, pct(p.nifty_return_1y));
    }
    out.push(`${line}.`);
  }
  if (counts) {
    const kept = counts.Kept ?? 0, decided = kept + (counts.Missed ?? 0);
    if (decided >= 3) out.push(t.summary.kept(kept, decided));
  }
  const r = m.results;
  if (r && r.revenue_yoy_pct != null && r.pat_yoy_pct != null) {
    out.push(t.summary.quarter(quarter(r.latest_quarter), r.bank, r.revenue_yoy_pct >= 0, pct(r.revenue_yoy_pct),
      r.pat_yoy_pct >= 0, pct(r.pat_yoy_pct)));
  }
  return out;
}

export function moveTitle(t: Dict, lang: Lang, f: MoveFacts): string {
  const up = f.change_pct >= 0;
  return t.move.title(up, pct(f.change_pct), dayMonthYear(f.date, lang)) + (f.biggest_in_year ? t.move.biggest(up) : "");
}

export function moveDetail(t: Dict, f: MoveFacts): string {
  let s = f.times != null ? t.move.times(f.times.toFixed(1)) : "";
  if (f.volume_x != null && f.volume_x >= 1.5) s += t.move.volume(f.volume_x.toFixed(1));
  if (f.nifty_change_pct != null) s += t.move.nifty(signedPct(f.nifty_change_pct));
  return s.trim();
}

/** -> [main text, detail or null] for one signal. */
export function signalText(t: Dict, lang: Lang, s: Signal): [string, string | null] {
  const f = s.facts as Record<string, never>;
  switch (s.key) {
    case "move":
      return [moveTitle(t, lang, s.facts as unknown as MoveFacts), moveDetail(t, s.facts as unknown as MoveFacts) || null];
    case "track":
      if (s.state === "none") return [t.signal.track.none, null];
      return [s.state === "few" ? t.signal.track.few(f.decided) : t.signal.track.enough(f.kept, f.decided),
        f.dropped ? t.signal.track.dropped(f.dropped) : null];
    case "price": {
      const r = f.return_1y as number, n = f.nifty_return_1y as number | null;
      const text = t.signal.price.year(r >= 0, pct(r)) + (n != null ? t.signal.price.nifty(n >= 0, pct(n)) : ".");
      const where = t.signal.price.where[s.state];
      return [text, where ? t.signal.price.detail(rupees(f.close), where, rupees(f.low_52w), rupees(f.high_52w)) : null];
    }
    case "delivery":
      return [t.signal.delivery.text(`${(f.recent as number).toFixed(0)}%`, `${(f.usual as number).toFixed(0)}%`, f.months),
        t.signal.delivery[s.state as "higher" | "lower" | "usual"]];
    case "filings":
      if (s.state === "clear") return [t.signal.filings.clear(f.days), null];
      return [t.signal.filings.flagged(f.count, f.days,
        (f.tags as unknown as string[]).map((x) => (t.filings.tag[x] ?? x).toLowerCase()).join(", ")), null];
  }
}
