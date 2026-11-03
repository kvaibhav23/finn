// Pure helpers for the digest and the alerts, kept apart from React so they can be tested with node --test.

import type { DigestItem } from "./types.ts";

export const WINDOWS = ["1", "3", "7", "30"] as const;
export type Window = (typeof WINDOWS)[number];
const HOUR = 3_600_000;

/** Start of a window that ends now: "1" is the last 24 hours. */
export const windowStart = (nowMs: number, w: Window) => nowMs - Number(w) * 24 * HOUR;

export interface Grouped { high: DigestItem[]; medium: DigestItem[]; low: DigestItem[] }

/** Filings filed at or after `startMs`, of the chosen types (null: every type), split by priority, newest first.
 * A results card shows once per company and quarter: a board meeting often files the results three times. */
export function group(items: DigestItem[], startMs: number, types: string[] | null): Grouped {
  const out: Grouped = { high: [], medium: [], low: [] };
  const carded = new Set<string>();
  for (const i of items) {
    if (Date.parse(i.filed_at) < startMs || (types && !types.includes(i.tag))) continue;
    let item = i;
    if (i.card) {
      const k = `${i.symbol}${i.card.qe}`;
      if (carded.has(k)) item = { ...i, card: undefined };   // shown above; null would mean "not in XBRL yet"
      carded.add(k);
    }
    (item.priority === 1 ? out.high : item.priority === 2 ? out.medium : out.low).push(item);
  }
  return out;
}

/** Routine filings (only counted, never listed) filed at or after `startMs`. */
export const routineCount = (routine: Record<string, string[]>, startMs: number, symbols?: Set<string>) =>
  Object.entries(routine).reduce((n, [s, times]) =>
    n + (symbols && !symbols.has(s) ? 0 : times.filter((t) => Date.parse(t) >= startMs).length), 0);

/** The newest filing before `startMs`, for "No filings since …". */
export const lastBefore = (items: DigestItem[], startMs: number) =>
  items.find((i) => Date.parse(i.filed_at) < startMs) ?? null;

/** [date, close, volume] for one company, oldest first. */
export type Session = [string, number, number];

export interface MoveAlert { kind: "move"; symbol: string; date: string; pct: number; volumeX: number | null; price: boolean }

export const VOLUME_DAYS = 50;
export const ALERT_SESSIONS = 20;

/** Days in the last `sessions` sessions where the close moved at least `rules.price` % on the day before, or the
 * volume was at least `rules.volume` times its average over the 50 sessions before. Newest first. */
export function moveAlerts(symbol: string, rows: Session[], rules: { price: number; volume: number },
  sessions = ALERT_SESSIONS): MoveAlert[] {
  const out: MoveAlert[] = [];
  for (let i = Math.max(1, rows.length - sessions); i < rows.length; i++) {
    const [date, close, volume] = rows[i];
    const prev = rows[i - 1][1];
    const pct = prev ? (close / prev - 1) * 100 : 0;
    const past = rows.slice(Math.max(0, i - VOLUME_DAYS), i).map((r) => r[2]).filter((v) => v > 0);
    const avg = past.length >= 20 ? past.reduce((a, b) => a + b, 0) / past.length : null;
    const volumeX = avg && volume ? volume / avg : null;
    const price = Math.abs(pct) >= rules.price;
    if (price || (volumeX != null && volumeX >= rules.volume)) out.push({ kind: "move", symbol, date, pct, volumeX, price });
  }
  return out.reverse();
}
