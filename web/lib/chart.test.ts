import assert from "node:assert/strict";
import { test } from "node:test";

import { around, biggestDays, nearest, periodReturns, rebase, sliceRange, thin, ticks, yearEarlier } from "./chart.ts";

const rows: [string, number][] = [
  ["2025-10-30", 1], ["2026-04-29", 2], ["2026-04-30", 3], ["2026-09-30", 4], ["2026-10-30", 5],
];

test("ranges count back calendar months from the last session", () => {
  assert.deepEqual(sliceRange(rows, "1M").map((r) => r[1]), [4, 5]);           // 30 Sep is the base for 30 Oct
  assert.deepEqual(sliceRange(rows, "6M").map((r) => r[1]), [3, 4, 5]);
  assert.equal(sliceRange(rows, "1Y").length, 5);
  const gap: [string, number][] = [["2026-03-27", 1], ["2026-04-01", 2], ["2026-05-01", 3]];
  assert.deepEqual(sliceRange(gap, "1M").map((r) => r[1]), [2, 3]);           // last session on or before 1 Apr
  assert.deepEqual(sliceRange([], "1Y"), []);
});

test("nearest point", () => {
  const xs = [0, 10, 20, 30];
  assert.equal(nearest(xs, -5), 0);
  assert.equal(nearest(xs, 14), 1);
  assert.equal(nearest(xs, 16), 2);
  assert.equal(nearest(xs, 99), 3);
  assert.equal(nearest([], 3), -1);
});

test("ticks are round and inside the range", () => {
  const t = ticks(3051, 4280);
  assert.ok(t.length >= 2 && t.every((v) => v >= 3051 && v <= 4280));
  assert.ok(t.every((v) => v % 250 === 0 || v % 500 === 0));
  assert.deepEqual(ticks(5, 5), [5]);
});

test("rebase", () => {
  assert.deepEqual(rebase([100, 110, 90], 50).map((v) => Math.round(v * 1e6) / 1e6), [50, 55, 45]);
  assert.deepEqual(rebase([], 50), []);
});

test("period returns compare the same two closes for the stock and the Nifty 50", () => {
  const r = periodReturns(rows, [["2026-09-30", 100], ["2026-10-30", 110], ["2025-10-30", 50]]);
  assert.deepEqual(r.map((x) => x.key), ["1M", "6M", "1Y"]);   // no session within a week of 23 Oct or 30 Jul
  assert.equal(r[0].from, "2026-09-30");
  assert.equal(Math.round(r[0].stock), 25);
  assert.equal(Math.round(r[0].nifty!), 10);
  assert.equal(r[1].nifty, null);                                             // no index close on 30 Apr
  assert.equal(Math.round(r[2].stock), 400);
  assert.deepEqual(periodReturns([["2026-01-01", 1]], null), []);
});

test("biggest days rank by size either way and carry the Nifty 50 only for consecutive sessions", () => {
  const p: [string, number][] = [["2026-01-01", 100], ["2026-01-02", 90], ["2026-01-05", 99], ["2026-01-06", 100]];
  const n: [string, number][] = [["2026-01-01", 1000], ["2026-01-02", 990], ["2026-01-06", 1000]];
  const d = biggestDays(p, n, 2);
  assert.deepEqual(d.map((x) => x.date), ["2026-01-05", "2026-01-02"]);
  assert.equal(Math.round(d[1].pct), -10);
  assert.equal(Math.round(d[1].nifty!), -1);
  assert.equal(d[0].nifty, null);                                             // no index close on 5 Jan
  assert.equal(biggestDays(p, n, 5).find((x) => x.date === "2026-01-06")!.nifty, null);  // previous index day isn't 5 Jan
});

test("thin keeps the ends; year-earlier quarter matches month and day", () => {
  const v = Array.from({ length: 250 }, (_, i) => i);
  const t = thin(v, 60);
  assert.equal(t.length, 60);
  assert.equal(t[0], 0);
  assert.equal(t.at(-1), 249);
  assert.deepEqual(thin([1, 2], 60), [1, 2]);
  const qes = ["2025-06-30", "2025-09-30", "2026-06-30", "2026-09-30"];
  assert.equal(yearEarlier(qes, 3), 1);
  assert.equal(yearEarlier(qes, 1), -1);
});

test("around a filing runs from the close before its date to the first close after it", () => {
  const r: [string, number][] = [["2026-10-14", 100], ["2026-10-15", 104], ["2026-10-16", 110], ["2026-10-19", 99]];
  const n: [string, number][] = [["2026-10-14", 200], ["2026-10-16", 202]];
  const a = around(r, n, "2026-10-15")!;
  assert.deepEqual([a.from, a.to], [["2026-10-14", 100], ["2026-10-16", 110]]);
  assert.equal(a.pct.toFixed(1), "10.0");
  assert.equal(a.nifty!.toFixed(1), "1.0");
  // Filed on a Saturday: Friday's close to Monday's. No Nifty close on Monday, so no comparison.
  const w = around(r, n, "2026-10-17")!;
  assert.deepEqual([w.from[0], w.to[0], w.nifty], ["2026-10-16", "2026-10-19", null]);
  assert.equal(around(r, n, "2026-10-19"), null);   // no session has closed since
  assert.equal(around(r, n, "2026-10-14"), null);   // no close before
});
