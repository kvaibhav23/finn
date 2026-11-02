"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

type Sym = [string, string];

let cache: Promise<Sym[]> | null = null;
const loadSymbols = () => (cache ??= fetch("/data/symbols.json").then((r) => r.json() as Promise<Sym[]>));

function rank(q: string, all: Sym[]): Sym[] {
  const u = q.trim().toUpperCase();
  if (!u) return [];
  const scored: [number, Sym][] = [];
  for (const s of all) {
    const [sym, name] = s;
    const n = name.toUpperCase();
    const score = sym === u ? 0 : sym.startsWith(u) ? 1 : n.startsWith(u) ? 2
      : n.split(/\s+/).some((w) => w.startsWith(u)) ? 3 : sym.includes(u) || n.includes(u) ? 4 : -1;
    if (score >= 0) scored.push([score, s]);
  }
  return scored.sort((a, b) => a[0] - b[0] || a[1][0].localeCompare(b[1][0])).slice(0, 8).map(([, s]) => s);
}

export function Search({ analysed, compact = false, autoFocus = false }:
  { analysed: string[]; compact?: boolean; autoFocus?: boolean }) {
  const router = useRouter();
  const id = useId();
  const [all, setAll] = useState<Sym[]>([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const done = useMemo(() => new Set(analysed), [analysed]);
  const results = useMemo(() => rank(q, all), [q, all]);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const go = (sym: string) => { setOpen(false); setQ(""); router.push(`/c/${encodeURIComponent(sym)}`); };

  return (
    <div className={`search${compact ? " compact" : ""}`} ref={box}>
      <label htmlFor={`${id}-q`} className="visually-hidden">Search any NSE company</label>
      <input
        id={`${id}-q`}
        type="search"
        role="combobox"
        aria-expanded={open && q.length > 0}
        aria-controls={`${id}-list`}
        aria-activedescendant={open && results[active] ? `${id}-o${active}` : undefined}
        autoComplete="off"
        spellCheck={false}
        autoFocus={autoFocus}
        placeholder={compact ? "Search company" : "Search any NSE company, e.g. Asian Paints or DIXON"}
        value={q}
        onFocus={() => { loadSymbols().then(setAll); setOpen(true); }}
        onChange={(e) => { setQ(e.target.value); setActive(0); setOpen(true); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          else if (e.key === "Enter" && results[active]) { e.preventDefault(); go(results[active][0]); }
          else if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && q.trim() && (
        <ul className="search-list" role="listbox" id={`${id}-list`}>
          {results.length === 0 && all.length > 0 && (
            <li className="search-empty" role="option" aria-selected={false}>No NSE company matches “{q.trim()}”.</li>
          )}
          {results.map(([sym, name], i) => (
            <li key={sym} id={`${id}-o${i}`} role="option" aria-selected={i === active}
                onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); go(sym); }}>
              <span className="opt-sym">{sym}</span>
              <span className="opt-name">{name}</span>
              {done.has(sym) && <span className="opt-tag">Ledger ready</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
