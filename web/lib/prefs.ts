"use client";

import { useEffect, useState } from "react";

// What the reader chose, kept on their device (no account): which filing types they care about (the digest and
// the alerts share it) and what counts as an unusual day. Read after mount, so the server render and the first
// client render agree and the saved choice is applied straight after.

export interface Rules { price: number; volume: number }

export const DEFAULT_RULES: Rules = { price: 5, volume: 2 };   // ±5% in a day; volume 2× its 50-day average
export const RULE_LIMITS = { price: { min: 0.5, max: 20, step: 0.5 }, volume: { min: 1.2, max: 10, step: 0.1 } };

const KEYS = { types: "finn_types", rules: "finn_rules", seen: "finn_alerts_seen" } as const;
const EVENT = "finn:prefs";

function read<T>(key: string, fallback: T, ok: (v: unknown) => boolean): T {
  try {
    const v = JSON.parse(localStorage.getItem(key) ?? "null");
    return v != null && ok(v) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    if (value == null) localStorage.removeItem(key); else localStorage.setItem(key, JSON.stringify(value));
  } catch { /* private mode: the choice lasts for this page only */ }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: key }));
}

function usePref<T>(key: string, fallback: T, ok: (v: unknown) => boolean): [T, (v: T | null) => void] {
  const [value, setValue] = useState<T>(fallback);
  useEffect(() => {
    const load = () => setValue(read(key, fallback, ok));
    load();
    const onChange = (e: Event) => { if ((e as CustomEvent<string>).detail === key) load(); };
    window.addEventListener(EVENT, onChange);
    window.addEventListener("storage", load);
    return () => { window.removeEventListener(EVENT, onChange); window.removeEventListener("storage", load); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return [value, (v) => write(key, v)];
}

/** Filing tags the reader cares about; null means every type. */
export const useTypes = () =>
  usePref<string[] | null>(KEYS.types, null, (v) => Array.isArray(v) && v.every((x) => typeof x === "string"));

const clamp = (n: number, { min, max }: { min: number; max: number }) => Math.min(max, Math.max(min, n));

export function useRules(): [Rules, (r: Rules | null) => void] {
  const [r, set] = usePref<Rules>(KEYS.rules, DEFAULT_RULES,
    (v) => typeof v === "object" && v != null && typeof (v as Rules).price === "number" && typeof (v as Rules).volume === "number");
  return [{ price: clamp(r.price, RULE_LIMITS.price), volume: clamp(r.volume, RULE_LIMITS.volume) }, set];
}

/** When the reader last marked their alerts as read (ISO time), or null. */
export const useSeen = () => usePref<string | null>(KEYS.seen, null, (v) => typeof v === "string");
