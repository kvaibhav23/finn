// Pure helpers for the price chart, kept apart from React so they can be tested with node --test.

export type Range = "1M" | "6M" | "1Y";
export const RANGES: Range[] = ["1M", "6M", "1Y"];
const MONTHS_BACK: Record<Range, number> = { "1M": 1, "6M": 6, "1Y": 12 };

const DAY = 86_400_000;
export const ms = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

/** Rows (oldest first, ISO date first) from the last session on or before the same calendar day `range`
 * before the last row, so "over a year" compares the same two closes as the summary above the chart. */
export function sliceRange<T extends [string, ...unknown[]]>(rows: T[], range: Range): T[] {
  if (!rows.length) return rows;
  const last = new Date(ms(rows[rows.length - 1][0]));
  last.setUTCMonth(last.getUTCMonth() - MONTHS_BACK[range]);
  const from = last.getTime();
  let start = 0;
  rows.forEach((r, i) => { if (ms(r[0]) <= from) start = i; });
  return rows.slice(start);
}

/** Index of the point whose x is nearest to `x` (xs ascending). */
export function nearest(xs: number[], x: number): number {
  let lo = 0, hi = xs.length - 1;
  if (hi < 0) return -1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid; else hi = mid;
  }
  return Math.abs(xs[hi] - x) < Math.abs(xs[lo] - x) ? hi : lo;
}

/** Three round price levels covering [min, max], for light gridlines. */
export function ticks(min: number, max: number, count = 3): number[] {
  if (!(max > min)) return [min];
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

/** Another series rebased so its first value equals `base` (to draw the Nifty 50 against the stock). */
export function rebase(values: number[], base: number): number[] {
  return values.length && values[0] ? values.map((v) => (v / values[0]) * base) : [];
}

export const days = (a: string, b: string) => Math.round((ms(b) - ms(a)) / DAY);

type Back = { months?: number; days?: number };

/** Index of the last row on or before the same calendar day `back` before the last row (as sliceRange). */
function startIndex(rows: [string, ...unknown[]][], back: Back): number {
  const last = new Date(ms(rows[rows.length - 1][0]));
  if (back.months) last.setUTCMonth(last.getUTCMonth() - back.months);
  if (back.days) last.setUTCDate(last.getUTCDate() - back.days);
  const from = last.getTime();
  let start = -1;
  rows.forEach((r, i) => { if (ms(r[0]) <= from) start = i; });
  // A gap in the history (more than a week before the start date) would measure a different period.
  return start >= 0 && from - ms(rows[start][0]) <= 7 * DAY ? start : -1;
}

export const PERIODS: [string, Back][] = [["1W", { days: 7 }], ["1M", { months: 1 }], ["3M", { months: 3 }],
  ["6M", { months: 6 }], ["1Y", { months: 12 }]];

export interface PeriodReturn { key: string; from: string; stock: number; nifty: number | null }

/** Percentage change in close over each period, and the Nifty 50's over the same two dates (null when the
 * index has no close on either date). A period the history doesn't cover is left out. */
export function periodReturns(rows: [string, number, ...unknown[]][], nifty: [string, number][] | null): PeriodReturn[] {
  if (rows.length < 2) return [];
  const idx = new Map(nifty ?? []);
  const end = rows[rows.length - 1];
  const out: PeriodReturn[] = [];
  for (const [key, back] of PERIODS) {
    const i = startIndex(rows, back);
    if (i < 0 || i === rows.length - 1) continue;
    const a = rows[i], na = idx.get(a[0]), nb = idx.get(end[0]);
    out.push({ key, from: a[0], stock: (end[1] / a[1] - 1) * 100, nifty: na && nb ? (nb / na - 1) * 100 : null });
  }
  return out;
}

export interface DayMove { date: string; pct: number; nifty: number | null }

/** The `n` largest one-day moves (by size, either way), biggest first, with the Nifty 50 on the same day. */
export function biggestDays(rows: [string, number, ...unknown[]][], nifty: [string, number][] | null, n = 5): DayMove[] {
  const idx = nifty ?? [];
  const pos = new Map(idx.map((r, i) => [r[0], i]));
  const out: DayMove[] = [];
  for (let i = 1; i < rows.length; i++) {
    const j = pos.get(rows[i][0]);
    const prev = j != null && j > 0 && idx[j - 1][0] === rows[i - 1][0] ? idx[j - 1][1] : null;
    out.push({ date: rows[i][0], pct: (rows[i][1] / rows[i - 1][1] - 1) * 100,
      nifty: j != null && prev ? (idx[j][1] / prev - 1) * 100 : null });
  }
  return out.sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct)).slice(0, n);
}

/** About `points` values spread evenly, always keeping the first and last (for small price lines). */
export function thin(values: number[], points = 60): number[] {
  if (values.length <= points) return values;
  const step = (values.length - 1) / (points - 1);
  return Array.from({ length: points }, (_, i) => values[Math.round(i * step)]);
}

/** Index of the quarter that ended a year before quarter `i` (same month and day), or -1. */
export function yearEarlier(qes: string[], i: number): number {
  const [y, rest] = [Number(qes[i].slice(0, 4)), qes[i].slice(4)];
  return qes.indexOf(`${y - 1}${rest}`);
}
