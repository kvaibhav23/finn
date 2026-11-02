import assert from "node:assert/strict";
import { test } from "node:test";

import { decide, parseTime, progress, type Run } from "./guards.ts";

const NOW = Date.parse("2026-11-02T06:00:00Z"); // 11:30 IST
const run = (name: string, status: string, created_at = "2026-11-02T05:00:00Z", conclusion: string | null = null): Run =>
  ({ id: 1, name, status, conclusion, created_at });

test("unknown symbols are refused", () => {
  assert.equal(decide({ symbol: "NOPE", known: false, entry: null, runs: [], now: NOW }).action, "unknown_symbol");
});

test("a fresh ledger is reused; a failed or stale one is not", () => {
  const fresh = { status: "ok", generated_at: "2026-10-30T10:00:00Z" };
  assert.equal(decide({ symbol: "X", known: true, entry: fresh, runs: [], now: NOW }).action, "ready");
  const failed = { status: "failed", generated_at: "2026-11-01T10:00:00Z" };
  assert.equal(decide({ symbol: "X", known: true, entry: failed, runs: [], now: NOW }).action, "dispatch");
  const stale = { status: "ok", generated_at: "2026-10-01T10:00:00" };   // old IST-format timestamp
  assert.equal(decide({ symbol: "X", known: true, entry: stale, runs: [], now: NOW }).action, "dispatch");
});

test("one analysis at a time, and a daily cap", () => {
  const busy = [run("ledger OTHER", "in_progress")];
  assert.equal(decide({ symbol: "X", known: true, entry: null, runs: busy, now: NOW }).action, "busy");
  const mine = [run("ledger X", "queued")];
  assert.equal(decide({ symbol: "X", known: true, entry: null, runs: mine, now: NOW }).action, "running");
  const many = Array.from({ length: 15 }, (_, i) => run(`ledger S${i}`, "completed", "2026-11-02T01:00:00Z", "success"));
  assert.equal(decide({ symbol: "X", known: true, entry: null, runs: many, now: NOW }).action, "limit");
  const yesterday = many.map((r) => ({ ...r, created_at: "2026-11-01T10:00:00Z" }));  // 15:30 IST on the 1st
  assert.equal(decide({ symbol: "X", known: true, entry: null, runs: yesterday, now: NOW }).action, "dispatch");
});

test("progress moves queued -> running -> publishing -> published", () => {
  assert.deepEqual(progress("X", [], null), { state: "none" });
  assert.deepEqual(progress("X", [run("ledger X", "queued")], null), { state: "queued" });
  assert.deepEqual(progress("X", [run("ledger X", "in_progress")], null, "Read earnings calls"),
    { state: "running", step: "Read earnings calls" });
  const done = [run("ledger X", "completed", "2026-11-02T05:00:00Z", "success")];
  assert.deepEqual(progress("X", done, null), { state: "publishing" });
  assert.deepEqual(progress("X", done, { status: "ok", generated_at: "2026-11-02T05:12:00Z" }),
    { state: "published", status: "ok" });
  assert.deepEqual(progress("X", done, { status: "ok", generated_at: "2026-10-01T05:12:00Z" }), { state: "publishing" });
  assert.deepEqual(progress("X", [run("ledger X", "completed", undefined, "cancelled")], null), { state: "failed" });
});

test("timestamps without a zone are IST", () => {
  assert.equal(parseTime("2026-11-02T11:30:00"), NOW);
  assert.equal(parseTime("2026-11-02T06:00:00Z"), NOW);
});
