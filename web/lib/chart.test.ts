import assert from "node:assert/strict";
import { test } from "node:test";

import { nearest, rebase, sliceRange, ticks } from "./chart.ts";

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
