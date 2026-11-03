"use client";

import Link from "next/link";
import { useState } from "react";

import { crore, rupees, signedPct } from "@/lib/format";
import { useT } from "@/lib/i18n/client";

import { Sparkline } from "./Sparkline";

export interface MonitorRow {
  symbol: string; name: string; close: number | null; day: number | null; m1: number | null; y1: number | null;
  spark: number[]; pe: number | null; cap: number | null; kept: number; decided: number; look: number | null;
}

type Key = "name" | "close" | "day" | "m1" | "y1" | "pe" | "cap" | "kept" | "look";

// A cell's tint grows with the size of the move (full at 20%), so the big movers stand out at a glance. Capped so
// the green or red figure on it stays readable.
const heat = (n: number | null) => n == null ? undefined
  : ({ "--heat": `${Math.round(Math.min(1, Math.abs(n) / 20) * 20 + 6)}%` } as React.CSSProperties);
const tone = (n: number | null) => (n == null ? "" : n > 0 ? "up" : n < 0 ? "down" : "");

/** Every company FINN covers in one table: price, moves, valuation, track record, filings to look at.
 * Each column sorts; each row opens the company. */
export function Monitor({ rows }: { rows: MonitorRow[] }) {
  const { t } = useT();
  const m = t.home.monitor, c = m.cols;
  const [sort, setSort] = useState<{ key: Key; desc: boolean }>({ key: "day", desc: true });

  const value = (r: MonitorRow, k: Key): number | string | null =>
    k === "name" ? r.name : k === "kept" ? (r.decided ? r.kept / r.decided : null) : r[k];
  const sorted = [...rows].sort((a, b) => {
    const x = value(a, sort.key), y = value(b, sort.key);
    if (x == null) return 1;
    if (y == null) return -1;
    const d = typeof x === "string" ? x.localeCompare(y as string) : x - (y as number);
    return sort.desc ? -d : d;
  });

  const head = (k: Key, label: string, num = true) => {
    const on = sort.key === k;
    return (
      <th scope="col" className={num ? "num" : ""} aria-sort={on ? (sort.desc ? "descending" : "ascending") : undefined}>
        <button type="button" onClick={() => setSort({ key: k, desc: on ? !sort.desc : k !== "name" })}>
          {label}<span className="sort" aria-hidden>{on ? (sort.desc ? "▼" : "▲") : ""}</span>
        </button>
      </th>
    );
  };
  const pct = (n: number | null, d = 1) => (n == null ? "" : signedPct(n, d));

  return (
    <div className="monitor-wrap">
      <table className="monitor">
        <caption className="visually-hidden">{m.title}</caption>
        <thead>
          <tr>
            {head("name", c.company, false)}
            {head("close", c.last)}
            {head("day", c.day)}
            {head("m1", c.m1)}
            {head("y1", c.y1)}
            <th scope="col" className="trend-col">{c.trend}</th>
            {head("pe", c.pe)}
            {head("cap", c.cap)}
            {head("kept", c.kept)}
            {head("look", c.look)}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.symbol}>
              <th scope="row">
                <Link href={`/c/${r.symbol}`}>
                  <span className="mon-sym">{r.symbol}</span>
                  <span className="mon-name">{r.name}</span>
                </Link>
              </th>
              <td className="num mon-last">{r.close != null ? rupees(r.close) : ""}</td>
              <td className={`num heat ${tone(r.day)}`} style={heat(r.day)}>{pct(r.day, 2)}</td>
              <td className={`num heat ${tone(r.m1)}`} style={heat(r.m1)}>{pct(r.m1)}</td>
              <td className={`num heat ${tone(r.y1)}`} style={heat(r.y1)}>{pct(r.y1)}</td>
              <td className="trend-col">{r.spark.length > 1 && <Sparkline values={r.spark} width={110} height={30} />}</td>
              <td className="num">{r.pe != null ? r.pe.toFixed(1) : ""}</td>
              <td className="num">{r.cap != null ? crore(r.cap, t.keys) : ""}</td>
              <td className="num">
                {r.decided > 0 && (
                  <span className="mon-kept">
                    {m.kept(r.kept, r.decided)}
                    <span className="mon-bar" aria-hidden><span style={{ width: `${(r.kept / r.decided) * 100}%` }} /></span>
                  </span>
                )}
              </td>
              <td className="num">{r.look ? <span className="look">{r.look}</span> : r.look === 0 ? <span className="mon-none">0</span> : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
