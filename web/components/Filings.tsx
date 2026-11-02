"use client";

import { useMemo, useState } from "react";

import { dayMonthYear } from "@/lib/format";
import type { Filing } from "@/lib/types";

const LOOK = "Worth a look";

/** Official NSE filings, newest first. Every row opens the company's own document on NSE. */
export function Filings({ filings, days }: { filings: Filing[]; days: number }) {
  const [tag, setTag] = useState<string>("All");
  const tags = useMemo(() => {
    const c = new Map<string, number>();
    filings.forEach((f) => c.set(f.tag, (c.get(f.tag) ?? 0) + 1));
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [filings]);
  const look = filings.filter((f) => f.worth_a_look).length;
  const shown = filings.filter((f) => tag === "All" || (tag === LOOK ? f.worth_a_look : f.tag === tag));

  if (!filings.length) {
    return <p className="empty">No filings in the last {days} days apart from routine paperwork.</p>;
  }
  return (
    <>
      <div className="seg seg-wrap" role="group" aria-label="Filter filings">
        <button type="button" aria-pressed={tag === "All"} onClick={() => setTag("All")}>All {filings.length}</button>
        {look > 0 && (
          <button type="button" aria-pressed={tag === LOOK} onClick={() => setTag(LOOK)}>{LOOK} {look}</button>
        )}
        {tags.map(([t, n]) => (
          <button key={t} type="button" aria-pressed={tag === t} onClick={() => setTag(t)}>{t} {n}</button>
        ))}
      </div>
      <ul className="filings">
        {shown.map((f, i) => (
          <li key={i} className="filing">
            <span className="filing-date">{dayMonthYear(f.date)}</span>
            <span className="filing-body">
              <span className="filing-tag">
                {f.tag}{f.worth_a_look && <span className="look">{LOOK}</span>}
              </span>
              <span className="filing-subject">{f.subject}</span>
            </span>
            <a className="filing-link" href={f.pdf_url} target="_blank" rel="noreferrer"
               aria-label={`Open the ${f.tag.toLowerCase()} filing of ${dayMonthYear(f.date)} on NSE`}>
              Open filing
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}
