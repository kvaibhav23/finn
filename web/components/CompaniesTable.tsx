"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { displayName, rupees, signedPct } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { IndexEntry } from "@/lib/types";

type Sort = "name" | "move" | "year" | "track";

const keptShare = (e: IndexEntry) => {
  const d = e.counts.Kept + e.counts.Missed;
  return d ? e.counts.Kept / d : -1;
};

export function CompaniesTable({ rows }: { rows: IndexEntry[] }) {
  const { t } = useT();
  const c = t.companies;
  const [sort, setSort] = useState<Sort>("name");
  const sorted = useMemo(() => {
    const by: Record<Sort, (a: IndexEntry, b: IndexEntry) => number> = {
      name: (a, b) => displayName(a.name, a.symbol).localeCompare(displayName(b.name, b.symbol)),
      move: (a, b) => Math.abs(b.change_pct ?? 0) - Math.abs(a.change_pct ?? 0),
      year: (a, b) => (b.return_1y ?? -1e9) - (a.return_1y ?? -1e9),
      track: (a, b) => keptShare(b) - keptShare(a),
    };
    return [...rows].sort(by[sort]);
  }, [rows, sort]);

  return (
    <>
      <div className="seg seg-wrap" role="group" aria-label={c.sortBy}>
        {(Object.keys(c.sort) as Sort[]).map((k) => (
          <button key={k} type="button" aria-pressed={sort === k} onClick={() => setSort(k)}>{c.sort[k]}</button>
        ))}
      </div>
      <table className="co-table">
        <thead>
          <tr>
            <th scope="col">{c.company}</th>
            <th scope="col" className="num">{c.price}</th>
            <th scope="col" className="num">{c.today}</th>
            <th scope="col" className="num">{c.year}</th>
            <th scope="col" className="num">{c.track}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((e) => {
            const decided = e.counts.Kept + e.counts.Missed;
            return (
              <tr key={e.symbol}>
                <th scope="row">
                  <Link href={`/c/${e.symbol}`}>{displayName(e.name, e.symbol)}</Link>
                  <span className="co-sym">{e.symbol}</span>
                  {e.big_move && <span className="look">{c.bigMove}</span>}
                </th>
                <td className="num">{e.close != null ? rupees(e.close) : ""}</td>
                <td className={`num ${e.change_pct == null ? "" : e.change_pct > 0 ? "up" : e.change_pct < 0 ? "down" : ""}`}>
                  {e.change_pct != null ? signedPct(e.change_pct, 2) : ""}
                </td>
                <td className="num">{e.return_1y != null ? signedPct(e.return_1y) : ""}</td>
                <td className="num">{decided ? c.trackOf(e.counts.Kept, decided) : ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
