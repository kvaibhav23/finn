// Pure rules for alert sign-ups (tested with node --test): what a valid request is, and how addresses are kept.

import { isLang, type Lang } from "../i18n/languages.ts";

export const EVENTS = ["move", "flag", "results", "ledger"] as const;
export type EventKind = (typeof EVENTS)[number];
export type Channel = "email" | "whatsapp";

export interface Subscriber {
  channel: Channel;
  address: string;            // lower-case email, or WhatsApp number as digits with country code (91XXXXXXXXXX)
  lang: Lang;
  confirmed: boolean;
  symbols: string[];
  events: EventKind[];
  created: string;
}

export function normalEmail(v: unknown): string | null {
  const s = String(v ?? "").trim().toLowerCase();
  return s.length <= 254 && /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/.test(s) ? s : null;
}

/** Indian mobile numbers only: 10 digits starting 6-9, with or without +91 / 0. -> "91XXXXXXXXXX" */
export function normalPhone(v: unknown): string | null {
  let d = String(v ?? "").replace(/[\s()-]/g, "");
  if (d.startsWith("+")) d = d.slice(1);
  if (!/^\d+$/.test(d)) return null;
  if (d.length === 12 && d.startsWith("91")) d = d.slice(2);
  else if (d.length === 11 && d.startsWith("0")) d = d.slice(1);
  return /^[6-9]\d{9}$/.test(d) ? `91${d}` : null;
}

export type SignupError = "email" | "phone" | "consent" | "events" | "symbol" | "channel";

export interface Signup { symbol: string; channel: Channel; address: string; events: EventKind[]; lang: Lang }

export function parseSignup(body: Record<string, unknown>): { ok: true; value: Signup } | { ok: false; error: SignupError } {
  const symbol = String(body.symbol ?? "").toUpperCase();
  if (!/^[A-Z0-9&_-]{1,20}$/.test(symbol)) return { ok: false, error: "symbol" };
  const channel = body.channel;
  if (channel !== "email" && channel !== "whatsapp") return { ok: false, error: "channel" };
  const address = channel === "email" ? normalEmail(body.address) : normalPhone(body.address);
  if (!address) return { ok: false, error: channel === "email" ? "email" : "phone" };
  const events = (Array.isArray(body.events) ? body.events : []).filter((e): e is EventKind => EVENTS.includes(e as EventKind));
  if (!events.length) return { ok: false, error: "events" };
  if (body.consent !== true) return { ok: false, error: "consent" };
  return { ok: true, value: { symbol, channel, address, events: [...new Set(events)], lang: isLang(body.lang) ? body.lang : "en" } };
}

/** Adds a company to an existing subscriber, or starts a new one (email waits for the confirmation click). */
export function merge(existing: Subscriber | null, s: Signup, now: string): Subscriber {
  if (existing) {
    return { ...existing, lang: s.lang, events: s.events, symbols: [...new Set([...existing.symbols, s.symbol])] };
  }
  return { channel: s.channel, address: s.address, lang: s.lang, confirmed: s.channel === "whatsapp",
    symbols: [s.symbol], events: s.events, created: now };
}

/** Who should get an event: confirmed, following the company, and asked for this kind of alert. */
export const wants = (sub: Subscriber, symbol: string, kind: EventKind) =>
  sub.confirmed && sub.symbols.includes(symbol) && sub.events.includes(kind);

/** "user@example.com" -> "u***@example.com", "919876543210" -> "+91 ******3210" (for logs and screens). */
export function mask(sub: Pick<Subscriber, "channel" | "address">): string {
  if (sub.channel === "email") {
    const [u, d] = sub.address.split("@");
    return `${u[0]}***@${d}`;
  }
  return `+91 ******${sub.address.slice(-4)}`;
}
