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
