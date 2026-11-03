"use client";

import { useMemo, useState } from "react";

import { dayMonthYear } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { Filing } from "@/lib/types";

const LOOK = "__look";

/** Official NSE filings, newest first. Every row opens the company's own document on NSE. */
export function Filings({ filings, days }: { filings: Filing[]; days: number }) {
  const { t, lang } = useT();
  const [tag, setTag] = useState<string>("All");
  const tags = useMemo(() => {
    const c = new Map<string, number>();
    filings.forEach((f) => c.set(f.tag, (c.get(f.tag) ?? 0) + 1));
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [filings]);
  const look = filings.filter((f) => f.worth_a_look).length;
  const shown = filings.filter((f) => tag === "All" || (tag === LOOK ? f.worth_a_look : f.tag === tag));

  if (!filings.length) {
    return <p className="empty">{t.filings.none(days)}</p>;
  }
  return (
    <>
      <div className="seg seg-wrap" role="group" aria-label={t.filings.filter}>
        <button type="button" aria-pressed={tag === "All"} onClick={() => setTag("All")}>{t.filings.all} {filings.length}</button>
        {look > 0 && (
          <button type="button" aria-pressed={tag === LOOK} onClick={() => setTag(LOOK)}>{t.filings.look} {look}</button>
        )}
        {tags.map(([x, n]) => (
          <button key={x} type="button" aria-pressed={tag === x} onClick={() => setTag(x)}>{t.filings.tag[x] ?? x} {n}</button>
        ))}
      </div>
      <ul className="filings">
        {shown.map((f, i) => (
          <li key={i} className="filing">
            <span className="filing-date">{dayMonthYear(f.date, lang)}</span>
            <span className="filing-body">
              <span className="filing-tag">
                {t.filings.tag[f.tag] ?? f.tag}{f.worth_a_look && <span className="look">{t.filings.look}</span>}
              </span>
              <span className="filing-subject" lang="en">{f.subject}</span>
            </span>
            <a className="filing-link" href={f.pdf_url} target="_blank" rel="noreferrer"
               aria-label={t.filings.openAria(t.filings.tag[f.tag] ?? f.tag, dayMonthYear(f.date, lang))}>
              {t.filings.open}
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}
