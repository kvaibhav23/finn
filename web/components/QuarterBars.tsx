"use client";

import { useState } from "react";

import { yearEarlier } from "@/lib/chart";
import { crore, quarter, signedPct } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { QuarterFigures } from "@/lib/types";

// One filed figure per quarter as bars: revenue, profit or margin (profit over revenue, both from the same
// filing). Choosing a quarter shows its value, the change on the same quarter a year earlier, and its filing.
type Metric = "revenue" | "pat" | "margin";
const H = 150, LABEL = 20;

export function QuarterBars({ quarters, topLine }: { quarters: QuarterFigures[]; topLine: string }) {
  const { t } = useT();
  const q = quarters.filter((x) => x.revenue_cr != null);
  const [metric, setMetric] = useState<Metric>("revenue");
  const [sel, setSel] = useState(q.length - 1);
  if (q.length < 2) return null;

  const b = t.keys.bars, v = t.view.quarters;
  const names: Record<Metric, string> = { revenue: topLine === "total_income" ? b.income : b.revenue, pat: b.pat, margin: v.margin };
  const value = (x: QuarterFigures): number | null =>
    metric === "revenue" ? x.revenue_cr : metric === "pat" ? x.pat_cr
      : x.pat_cr != null && x.revenue_cr ? (x.pat_cr / x.revenue_cr) * 100 : null;
  const show = (n: number | null) => n == null ? v.notFiled : metric === "margin" ? `${n.toFixed(1)}%` : crore(n, t.keys);

  const vals = q.map(value);
  const hi = Math.max(0, ...vals.map((n) => n ?? 0)), lo = Math.min(0, ...vals.map((n) => n ?? 0));
  const span = hi - lo || 1;
  const base = (hi / span) * (H - LABEL);
  const h = (n: number) => (Math.abs(n) / span) * (H - LABEL);
  const step = 100 / q.length;

  const cur = q[sel], now = vals[sel];
  const j = yearEarlier(q.map((x) => x.qe), sel);
  const then = j >= 0 ? vals[j] : null;
  const change = now == null || then == null ? null
    : metric === "margin" ? v.marginYoy(t.view.returns.pts(signedPct(now - then).replace("%", "")), quarter(q[j].quarter))
      : then > 0 ? v.yoy(signedPct((now / then - 1) * 100), quarter(q[j].quarter)) : null;

  const key = (e: React.KeyboardEvent) => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    setSel((i) => Math.max(0, Math.min(q.length - 1, i + d)));
  };

  return (
    <figure className="qchart">
      <div className="chart-head">
        <p className="chart-read" aria-live="polite">
          <b>{quarter(cur.quarter)}: {show(now)}</b>
          <span className="chart-sub">{change ? `, ${change}` : j < 0 ? `, ${v.noYoy}` : ""}</span>
          {cur.xbrl_url && (
            <span className="chart-sub">. <a href={cur.xbrl_url} target="_blank" rel="noreferrer">{t.ledger.xbrl}</a></span>
          )}
        </p>
        <div className="seg" role="group" aria-label={v.show}>
          {(Object.keys(names) as Metric[]).map((m) => (
            <button key={m} type="button" aria-pressed={metric === m} onClick={() => setMetric(m)}>{names[m]}</button>
          ))}
        </div>
      </div>
      <svg width="100%" height={H} role="group" aria-label={`${names[metric]}, ${b.caption}`} tabIndex={0} onKeyDown={key}
           className="qchart-svg">
        <line x1="0" x2="100%" y1={base} y2={base} stroke="var(--rule)" />
        {q.map((x, i) => {
          const n = vals[i];
          return (
            <svg key={x.qe} x={`${step * i}%`} width={`${step}%`} height={H} overflow="visible">
              <rect x="0" y="0" width="100%" height={H} fill="transparent" className="qhit" onClick={() => setSel(i)}
                    onPointerEnter={(e) => e.pointerType === "mouse" && setSel(i)} />
              {n != null && (
                <rect x="22%" width="56%" y={n >= 0 ? base - h(n) : base} height={Math.max(1, h(n))} pointerEvents="none"
                      className={`qbar${i === sel ? " on" : ""}${n < 0 ? " loss" : ""}`} />
              )}
              <text x="50%" y={H - 5} textAnchor="middle" pointerEvents="none"
                    className={`chart-tick${i === sel ? " on" : ""}`}>{quarter(x.quarter)}</text>
            </svg>
          );
        })}
      </svg>
      <figcaption className="chart-sub">{v.tap}</figcaption>
      <table className="visually-hidden">
        <caption>{names[metric]}, {b.caption}</caption>
        <thead><tr><th>{b.quarter}</th><th>{names[metric]}</th></tr></thead>
        <tbody>
          {q.map((x, i) => <tr key={x.qe}><td>{quarter(x.quarter)}</td><td>{show(vals[i])}</td></tr>)}
        </tbody>
      </table>
    </figure>
  );
}
