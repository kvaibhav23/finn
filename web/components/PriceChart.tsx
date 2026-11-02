"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { RANGES, ms, nearest, rebase, sliceRange, ticks, type Range } from "@/lib/chart";
import { dayMonthYear, quarter, rupees, signedPct } from "@/lib/format";
import type { CallDate, PriceRow } from "@/lib/types";

// End-of-day closes as one thin line. The only marks on it are the earnings calls FINN read: tapping one
// opens the promises made on that call, so what management said sits next to what the stock did after.
const H = 240, TOP = 16, BOTTOM = 34, RIGHT = 64;
const RANGE_WORDS: Record<Range, string> = { "1M": "a month", "6M": "6 months", "1Y": "a year" };

export function PriceChart({ rows, nifty, calls, ledgerQuarters, adjustedFor }: {
  rows: PriceRow[];
  nifty: [string, number][] | null;
  calls: CallDate[];
  ledgerQuarters: string[];
  adjustedFor: string[];
}) {
  const [range, setRange] = useState<Range>("1Y");
  const [compare, setCompare] = useState(false);
  const [at, setAt] = useState<number | null>(null);
  const [width, setWidth] = useState(960);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const shown = useMemo(() => sliceRange(rows, range), [rows, range]);
  const closes = shown.map((r) => r[1]);
  const niftyShown = useMemo(() => {
    if (!compare || !nifty?.length || !shown.length) return [];
    const byDate = new Map(nifty);
    const pairs = shown.filter((r) => byDate.has(r[0])).map((r) => [r[0], byDate.get(r[0])!] as const);
    const base = shown.find((r) => byDate.has(r[0]))?.[1] ?? shown[0][1];
    const values = rebase(pairs.map((p) => p[1]), base);
    return pairs.map((p, i) => [p[0], values[i]] as const);
  }, [compare, nifty, shown]);

  if (shown.length < 2) return null;

  const all = [...closes, ...niftyShown.map((n) => n[1])];
  const lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.08 || hi * 0.02;
  const y0 = lo - pad, y1 = hi + pad;
  const t0 = ms(shown[0][0]), t1 = ms(shown[shown.length - 1][0]);
  const plotW = width - RIGHT;
  const x = (iso: string) => ((ms(iso) - t0) / (t1 - t0 || 1)) * plotW;
  const y = (v: number) => TOP + (1 - (v - y0) / (y1 - y0)) * (H - TOP - BOTTOM);
  const xs = shown.map((r) => x(r[0]));
  const path = (pts: readonly (readonly [string, number])[]) =>
    pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");

  const first = closes[0], last = closes[closes.length - 1];
  const point = at != null ? shown[at] : null;
  const marks = calls.filter((c) => ms(c.date) >= t0 && ms(c.date) <= t1);
  // Labels shorten on narrow screens, and one that would overlap its neighbour is left out (its line stays).
  const roomy = plotW / Math.max(1, marks.length) >= 96;
  const placed: { c: CallDate; left: number; text: string }[] = [];
  for (const c of marks) {
    const text = roomy ? `${quarter(c.quarter)} call` : quarter(c.quarter);
    const w = text.length * 6.6 + 14;
    const left = Math.min(Math.max(x(c.date), w / 2), plotW - w / 2);
    const prev = placed[placed.length - 1];
    if (prev && left - w / 2 < prev.left + (prev.text.length * 6.6 + 14) / 2 + 4) continue;
    placed.push({ c, left, text });
  }
  const label = `Closing price over ${RANGE_WORDS[range]}: ${rupees(first)} on ${dayMonthYear(shown[0][0])} to `
    + `${rupees(last)} on ${dayMonthYear(shown[shown.length - 1][0])}, ${signedPct((last / first - 1) * 100)}.`;

  const move = (clientX: number) => {
    const rect = box.current?.getBoundingClientRect();
    if (!rect) return;
    setAt(nearest(xs, clientX - rect.left));
  };
  const key = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const step = e.shiftKey ? 10 : 1;
    setAt((i) => Math.max(0, Math.min(shown.length - 1, (i ?? shown.length - 1) + (e.key === "ArrowLeft" ? -step : step))));
  };
  const openCall = (q: string) => {
    window.dispatchEvent(new CustomEvent("finn:made", { detail: q }));
    document.getElementById("promises")?.scrollIntoView({ block: "start" });
  };

  return (
    <div className="chart">
      <div className="chart-head">
        <p className="chart-read" aria-live="polite">
          {point ? (
            <><b>{rupees(point[1])}</b> on {dayMonthYear(point[0])}
              {point[3] != null && <span className="chart-sub">, {point[3].toFixed(0)}% delivered</span>}</>
          ) : (
            <><b>{signedPct((last / first - 1) * 100)}</b> over {RANGE_WORDS[range]}</>
          )}
        </p>
        <div className="seg" role="group" aria-label="Time range">
          {RANGES.map((r) => (
            <button key={r} type="button" aria-pressed={range === r} onClick={() => { setRange(r); setAt(null); }}>{r}</button>
          ))}
        </div>
      </div>

      <div className="chart-box" ref={box} onPointerLeave={() => setAt(null)}>
        <svg width={width} height={H} role="img" aria-label={label} tabIndex={0} onKeyDown={key}
             onPointerMove={(e) => move(e.clientX)} onPointerDown={(e) => move(e.clientX)} onBlur={() => setAt(null)}>
          {ticks(y0, y1).map((v) => (
            <g key={v}>
              <line x1={0} x2={plotW} y1={y(v)} y2={y(v)} stroke="var(--rule)" />
              <text x={plotW + 8} y={y(v) + 4} className="chart-tick">{v.toLocaleString("en-IN")}</text>
            </g>
          ))}
          {marks.map((c) => (
            <line key={c.quarter} x1={x(c.date)} x2={x(c.date)} y1={TOP} y2={H - BOTTOM} stroke="var(--rule)"
                  strokeDasharray="2 3" />
          ))}
          {niftyShown.length > 1 && (
            <path d={path(niftyShown)} fill="none" stroke="var(--faint)" strokeWidth={1.2} strokeDasharray="3 3" />
          )}
          <path d={path(shown.map((r) => [r[0], r[1]] as const))} fill="none" stroke="var(--ink)" strokeWidth={1.6}
                strokeLinejoin="round" />
          {point && at != null && (
            <g>
              <line x1={xs[at]} x2={xs[at]} y1={TOP} y2={H - BOTTOM} stroke="var(--quiet)" />
              <circle cx={xs[at]} cy={y(point[1])} r={4} fill="var(--paper)" stroke="var(--ink)" strokeWidth={1.6} />
            </g>
          )}
        </svg>
        <div className="chart-calls" style={{ width: plotW }}>
          {placed.map(({ c, left, text }) => {
            const inLedger = ledgerQuarters.includes(c.quarter);
            return inLedger ? (
              <button key={c.quarter} type="button" className="call-mark" style={{ left }} onClick={() => openCall(c.quarter)}
                      title={`See the promises made on the ${quarter(c.quarter)} earnings call (${dayMonthYear(c.date)})`}>
                {text}
              </button>
            ) : (
              <span key={c.quarter} className="call-mark off" style={{ left }}
                    title={`${quarter(c.quarter)} earnings call, ${dayMonthYear(c.date)}`}>
                {text}
              </span>
            );
          })}
        </div>
      </div>

      <div className="chart-foot">
        {nifty?.length ? (
          <label className="check">
            <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} /> Compare with
            Nifty 50 <span className="chart-sub">(dashed, started at the same price)</span>
          </label>
        ) : <span />}
        <span className="chart-sub">
          Daily closing prices from NSE.{adjustedFor.length ? ` Adjusted for ${adjustedFor.join(", ")}.` : ""}
          {marks.length ? " Dotted lines mark earnings calls; tap one to read what was promised." : ""}
        </span>
      </div>
    </div>
  );
}
