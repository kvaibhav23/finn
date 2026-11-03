import assert from "node:assert/strict";
import { test } from "node:test";

import { emailText, message } from "./alerts/messages.ts";
import { merge, normalEmail, normalPhone, parseSignup, wants } from "./alerts/core.ts";
import { en } from "./i18n/en.ts";
import { moveTitle, signalText, summary } from "./sentences.ts";
import type { Market, Signal } from "./types.ts";

const market = {
  price: { close: 3412.5, as_of: "2026-10-30", return_1y: -8.24, nifty_return_1y: 6.1 },
  results: { latest_quarter: "Q2FY27", revenue_yoy_pct: 5.04, pat_yoy_pct: -2.0, bank: false },
} as unknown as Market;

test("summary sentences need their facts", () => {
  assert.deepEqual(summary(en, "en", "TCS", market, { Kept: 4, Missed: 1 }), [
    "TCS closed at ₹3,412.50 on 30 Oct 2026, down 8.2% over the year, while the Nifty 50 rose 6.1%.",
    "Management kept 4 of the 5 promises FINN could check against results.",
    "In Q2 FY27, revenue grew 5.0% and profit fell 2.0% on a year earlier.",
  ]);
  const thin = { price: { ...market.price!, nifty_return_1y: null }, results: { ...market.results!, pat_yoy_pct: null } } as unknown as Market;
  assert.deepEqual(summary(en, "en", "TCS", thin, { Kept: 1, Missed: 1 }),
    ["TCS closed at ₹3,412.50 on 30 Oct 2026, down 8.2% over the year."]);
});

test("signal sentences from facts and state", () => {
  const track: Signal = { key: "track", state: "enough", facts: { kept: 4, missed: 1, decided: 5, dropped: 1 } };
  assert.deepEqual(signalText(en, "en", track), ["Kept 4 of the 5 promises whose results are in.", "1 more was never mentioned again."]);
  const price: Signal = { key: "price", state: "low",
    facts: { return_1y: -8.24, nifty_return_1y: 6.1, close: 3412.5, low_52w: 3300, high_52w: 4280 } };
  assert.equal(signalText(en, "en", price)[0], "Down 8.2% in a year; the Nifty 50 rose 6.1% over the same days.");
  assert.match(signalText(en, "en", price)[1]!, /near its 52-week low/);
  const filings: Signal = { key: "filings", state: "flagged", facts: { count: 1, days: 90, tags: ["Auditor change"] } };
  assert.equal(signalText(en, "en", filings)[0], "1 filing worth a look in the last 90 days: auditor change.");
});

test("big move wording", () => {
  const f = { date: "2026-11-02", change_pct: -12.04, typical_pct: 1.2, times: 10, volume_x: 4, biggest_in_year: true, nifty_change_pct: -0.4 };
  assert.equal(moveTitle(en, "en", f), "Fell 12.0% on 2 Nov 2026, its biggest one-day fall in a year");
});

test("other languages format dates with 0-9 digits", () => {
  assert.match(moveTitle(en, "bn", { date: "2026-11-02", change_pct: 6, typical_pct: 1, times: null, volume_x: null,
    biggest_in_year: false, nifty_change_pct: null }), /2026/);
});

test("alert sign-up rules", () => {
  assert.equal(normalEmail(" A@Example.COM "), "a@example.com");
  assert.equal(normalEmail("nope"), null);
  assert.equal(normalPhone("+91 98765 43210"), "919876543210");
  assert.equal(normalPhone("09876543210"), "919876543210");
  assert.equal(normalPhone("12345"), null);
  assert.equal(normalPhone("5876543210"), null);           // Indian mobiles start 6-9
  const bad = parseSignup({ symbol: "TCS", channel: "email", address: "a@b.co", events: ["move"], consent: false });
  assert.deepEqual(bad, { ok: false, error: "consent" });
  const ok = parseSignup({ symbol: "tcs", channel: "whatsapp", address: "9876543210", events: ["move", "x"], consent: true, lang: "hi" });
  assert.ok(ok.ok && ok.value.symbol === "TCS" && ok.value.events.join() === "move" && ok.value.lang === "hi");
  if (!ok.ok) return;
  const sub = merge(null, ok.value, "now");
  assert.equal(sub.confirmed, true);                        // WhatsApp: consent given on the form
  const emailSub = merge(null, { ...ok.value, channel: "email", address: "a@b.co" }, "now");
  assert.equal(emailSub.confirmed, false);                  // email waits for the confirmation click
  assert.ok(wants(sub, "TCS", "move") && !wants(sub, "TCS", "flag") && !wants(emailSub, "TCS", "move"));
  const more = merge(sub, { ...ok.value, symbol: "INFY" }, "later");
  assert.deepEqual(more.symbols, ["TCS", "INFY"]);
});

test("alert messages", () => {
  const m = message(en, "en", { id: "x", symbol: "TCS", kind: "move", date: "2026-11-02",
    facts: { change_pct: -7.1, times: 4.2, biggest_in_year: true } }, "Tata Consultancy Services", "https://finn.example");
  assert.equal(m.subject, "TCS fell 7.1% today");
  assert.equal(m.text, "Tata Consultancy Services fell 7.1% on 2 Nov 2026, its biggest one-day fall in a year. That is about 4.2 times its usual daily move.");
  assert.equal(m.link, "https://finn.example/c/TCS#overview");
  const txt = emailText(en, m, "TCS", "https://u/1", "https://u/all");
  assert.match(txt, /Stop alerts about TCS: https:\/\/u\/1/);
  const r = message(en, "en", { id: "y", symbol: "TCS", kind: "flag", date: "2026-11-02",
    facts: { tag: "Auditor change", pdf_url: "https://nse/x.pdf" } }, "TCS", "https://f");
  assert.equal(r.filing, "https://nse/x.pdf");
});
