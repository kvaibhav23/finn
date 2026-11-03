"use client";

import Link from "next/link";
import { useState } from "react";

import { crisp, dayMonthYear, dayTime } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { Dict, Lang } from "@/lib/i18n";
import { useTypes } from "@/lib/prefs";
import type { Digest as DigestData, DigestItem, Profile } from "@/lib/types";
import { WINDOWS, group, lastBefore, routineCount, windowStart, type Window } from "@/lib/watch";

import { ResultsCard } from "./ResultsCard";

const PEOPLE = new Set(["Appointment", "Resignation"]);

/** Every filing across the companies FINN watches, for a window the reader picks, most important first. */
export function Digest({ digest, now, initial = "1" }: { digest: DigestData; now: number; initial?: Window }) {
  const { t, lang } = useT();
  const d = t.digest;
  const [win, setWin] = useState<Window | "since">(initial);
  const [since, setSince] = useState("");
  const [types, setTypes] = useTypes();
  const [showLow, setShowLow] = useState(false);

  const start = win === "since" && since ? Date.parse(`${since}T00:00:00+05:30`) : windowStart(now, win === "since" ? "30" : win);
  const g = group(digest.items, start, types);
  const n = g.high.length + g.medium.length + g.low.length;
  const companies = new Set([...g.high, ...g.medium, ...g.low].map((i) => i.symbol)).size;
  const routine = routineCount(digest.routine, start);
  const tags = [...new Set(digest.items.map((i) => i.tag))].sort((a, b) =>
    (digest.items.find((i) => i.tag === a)!.priority - digest.items.find((i) => i.tag === b)!.priority) || a.localeCompare(b));
  const wider = WINDOWS.find((w) => win !== "since" && Number(w) > Number(win));
  const prev = lastBefore(digest.items, start);
  const oldest = digest.items.at(-1)?.filed_at.slice(0, 10);

  // The address keeps the window (/digest?w=7), so a view can be shared or bookmarked.
  const choose = (w: Window) => {
    setWin(w);
    history.replaceState(null, "", w === "1" ? location.pathname : `?w=${w}`);
  };

  const toggle = (tag: string) => {
    const cur = new Set(types ?? tags);
    if (cur.has(tag)) cur.delete(tag); else cur.add(tag);
    setTypes(cur.size === tags.length || cur.size === 0 ? null : [...cur]);
  };

  return (
    <>
      <div className="dg-controls">
        <div className="dg-row">
          <span className="dg-label" id="dg-period">{d.period}</span>
          <div className="seg" role="group" aria-labelledby="dg-period">
            {WINDOWS.map((w) => (
              <button key={w} type="button" aria-pressed={win === w} onClick={() => choose(w)}>{d.windows[w]}</button>
            ))}
          </div>
          <label className="dg-since">
            {d.since}
            <input type="date" value={since} min={oldest} max={new Date(now).toISOString().slice(0, 10)}
                   onChange={(e) => { setSince(e.target.value); setWin(e.target.value ? "since" : "1"); }} />
          </label>
        </div>
        <div className="dg-row">
          <span className="dg-label" id="dg-types">{d.types}</span>
          <div className="chips" role="group" aria-labelledby="dg-types">
            <button type="button" aria-pressed={types == null} onClick={() => setTypes(null)}>{d.allTypes}</button>
            {tags.map((tag) => (
              <button key={tag} type="button" aria-pressed={types != null && types.includes(tag)} onClick={() => toggle(tag)}>
                {t.filings.tag[tag] ?? tag}
              </button>
            ))}
          </div>
        </div>
        <p className="small-print dg-hint">{d.typesHint}</p>
      </div>

      <p className="dg-count" aria-live="polite">
        {d.count(n, companies)}
        {digest.as_of && <span className="dg-asof"> {d.asOf(dayTime(digest.as_of, lang))}</span>}
      </p>

      {n === 0 ? (
        <div className="dg-empty">
          <p>{d.empty(prev ? dayTime(prev.filed_at, lang) : dayMonthYear(new Date(start).toISOString(), lang))}</p>
          {wider && <button type="button" className="btn-quiet" onClick={() => choose(wider)}>{d.widen(d.windows[wider])}</button>}
        </div>
      ) : (
        <>
          {g.high.length > 0 && (
            <section className="dg-group p1" aria-labelledby="dg-high">
              <h2 className="dg-title" id="dg-high">{d.high} <span className="n">{g.high.length}</span></h2>
              <p className="section-sub">{d.highSub}</p>
              <ol className="dg-list">{g.high.map((i) => <Item key={i.pdf_url} i={i} t={t} lang={lang} rich />)}</ol>
            </section>
          )}
          {g.medium.length > 0 && (
            <section className="dg-group p2" aria-labelledby="dg-medium">
              <h2 className="dg-title" id="dg-medium">{d.medium} <span className="n">{g.medium.length}</span></h2>
              <p className="section-sub">{d.mediumSub}</p>
              <ol className="dg-list">{g.medium.map((i) => <Item key={i.pdf_url} i={i} t={t} lang={lang} />)}</ol>
            </section>
          )}
          {g.low.length > 0 && (
            <section className="dg-group p3">
              <button type="button" className="dg-more" aria-expanded={showLow} onClick={() => setShowLow(!showLow)}>
                {d.low(g.low.length)} <span aria-hidden>{showLow ? "−" : "+"}</span>
              </button>
              {showLow && <ol className="dg-list">{g.low.map((i) => <Item key={i.pdf_url} i={i} t={t} lang={lang} />)}</ol>}
            </section>
          )}
        </>
      )}
      {routine > 0 && <p className="small-print">{d.routine(routine)}</p>}
    </>
  );
}

function Item({ i, t, lang, rich = false }: { i: DigestItem; t: Dict; lang: Lang; rich?: boolean }) {
  const d = t.digest;
  return (
    <li className={`dg-item t-${i.tag.split(" ")[0].toLowerCase()}`}>
      <div className="dg-meta">
        <time dateTime={i.filed_at}>{dayTime(i.filed_at, lang)}</time>
        <Link href={`/c/${i.symbol}`} className="feed-sym">{i.symbol}</Link>
        <span className="dg-tag">{t.filings.tag[i.tag] ?? i.tag}</span>
      </div>
      <a className="dg-text" href={i.pdf_url} target="_blank" rel="noreferrer" lang="en">{crisp(i.subject)}</a>
      {rich && i.tag === "Results" && (i.card ? <ResultsCard card={i.card} t={t} compact />
        : i.card === null && <p className="small-print">{t.results.pending}</p>)}
      {rich && PEOPLE.has(i.tag) && (i.profile ? <Person p={i.profile} pdf={i.pdf_url} t={t} /> : <p className="small-print">{d.noProfile}</p>)}
    </li>
  );
}

function Person({ p, pdf, t }: { p: Profile; pdf: string; t: Dict }) {
  const d = t.digest;
  return (
    <div className="dg-person">
      <p className="dg-person-h">{d.profile}</p>
      {p.name && (
        <p className="dg-who" lang="en">
          <b>{p.name}</b>{p.role ? `, ${p.role}` : ""}{p.effective && <span className="dg-when"> {d.from(p.effective)}</span>}
        </p>
      )}
      {p.previous && p.previous.length > 0 && (
        <p className="dg-prev"><span className="dg-label">{d.before}</span> <span lang="en">{p.previous.join("; ")}</span></p>
      )}
      {p.excerpt && <blockquote className="dg-excerpt" lang="en">{p.excerpt}</blockquote>}
      <p className="small-print"><a href={`${pdf}#page=${p.page}`} target="_blank" rel="noreferrer">{d.open}, {d.page(p.page)}</a></p>
    </div>
  );
}
