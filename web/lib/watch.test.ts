import assert from "node:assert/strict";
import { test } from "node:test";

import type { DigestItem } from "./types.ts";
import { group, lastBefore, moveAlerts, routineCount, windowStart, type Session } from "./watch.ts";

const item = (symbol: string, filed_at: string, tag: string, priority: 1 | 2 | 3, card = false): DigestItem => ({
  symbol, name: symbol, filed_at, tag, priority, subject: tag, pdf_url: `p${filed_at}`,
  card: card ? { quarter: "Q2FY27", qe: "2026-09-30", approved: null, basis: null, xbrl_url: null,
                 prev_quarter: null, year_quarter: null, rows: [] } : null,
});
const NOW = Date.parse("2026-11-03T20:00:00+05:30");
const items = [
  item("AAA", "2026-11-03T18:00:00+05:30", "Results", 1, true),
  item("AAA", "2026-11-03T17:59:00+05:30", "Results", 1, true),
  item("BBB", "2026-11-03T09:00:00+05:30", "Order or contract", 2),
  item("CCC", "2026-11-02T21:00:00+05:30", "Board meeting", 3),
  item("DDD", "2026-10-30T10:00:00+05:30", "Appointment", 1),
];

test("the 24-hour window splits by priority and shows a results card once", () => {
  const g = group(items, windowStart(NOW, "1"), null);
  assert.equal(g.high.length, 2);
  assert.ok(g.high[0].card && g.high[1].card === undefined);
  assert.equal(g.medium.length, 1);
  assert.equal(g.low.length, 1);                                    // 21:00 yesterday is inside 24 hours
});

test("the chosen types filter every group; a wider window reaches older filings", () => {
  const g = group(items, windowStart(NOW, "7"), ["Appointment"]);
  assert.deepEqual([g.high.length, g.medium.length, g.low.length], [1, 0, 0]);
  assert.equal(lastBefore(items, windowStart(NOW, "1"))?.symbol, "DDD");
});

test("routine filings are counted inside the window only", () => {
  const r = { AAA: ["2026-11-03T10:00:00+05:30", "2026-10-01T10:00:00+05:30"], BBB: ["2026-11-03T11:00:00+05:30"] };
  assert.equal(routineCount(r, windowStart(NOW, "1")), 2);
  assert.equal(routineCount(r, windowStart(NOW, "1"), new Set(["AAA"])), 1);
});

test("move alerts follow the reader's thresholds", () => {
  const rows: Session[] = Array.from({ length: 60 }, (_, i) => [`2026-08-${String(i).padStart(2, "0")}`, 100, 1000]);
  rows.push(["2026-10-29", 106, 1000]);                             // +6%, usual volume
  rows.push(["2026-10-30", 106.5, 2500]);                           // small move, 2.5x volume
  const loose = moveAlerts("AAA", rows, { price: 5, volume: 2 });
  assert.deepEqual(loose.map((a) => a.date), ["2026-10-30", "2026-10-29"]);
  assert.ok(loose[1].price && !loose[0].price);
  assert.ok(Math.abs(loose[0].volumeX! - 2.5) < 0.01);
  assert.deepEqual(moveAlerts("AAA", rows, { price: 7, volume: 3 }), []);
});
