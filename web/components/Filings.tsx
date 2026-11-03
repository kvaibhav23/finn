"use client";

import { useMemo, useState } from "react";

import { around, ms } from "@/lib/chart";
import { dayMonthYear, monthShort, monthYear, rupees, signedPct } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { Filing, PriceRow } from "@/lib/types";

const LOOK = "__look";
const DAY = 86_400_000;
const H = 156, TOP = 10, LINE_H = 78, BASE = 134, MARK = 6, MAX_STACK = 5;

type Props = { filings: Filing[]; days: number; rows: PriceRow[]; nifty: [string, number][] | null; end: string | null };

/** Official NSE filings, newest first. A timeline of the window (price line above, one square per filing
 * below) is linked to the list: pointing at a filing in either shows it in the other, with what the price
 * did across its date. Every row still opens the company's own document on NSE in one click. */
export function Filings({ filings, days, rows, nifty, end }: Props) {
  const { t, lang } = useT();
  const f = t.filings;
  const [tag, setTag] = useState<string>("All");
  const [query, setQuery] = useState("");
  const [sel, setSel] = useState<number | null>(filings.length ? 0 : null);
  const [open, setOpen] = useState<Set<number>>(new Set());

  const tags = useMemo(() => {
    const c = new Map<string, number>();
    filings.forEach((x) => c.set(x.tag, (c.get(x.tag) ?? 0) + 1));
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [filings]);
  const look = filings.filter((x) => x.worth_a_look).length;
  const label = (x: Filing) => f.tag[x.tag] ?? x.tag;

  const q = query.trim().toLowerCase();
  const match = (x: Filing) => (tag === "All" || (tag === LOOK ? x.worth_a_look : x.tag === tag))
    && (!q || `${x.subject} ${x.category} ${x.tag} ${label(x)}`.toLowerCase().includes(q));
  const shown = filings.map((x, i) => i).filter((i) => match(filings[i]));

  if (!filings.length) return <p className="empty">{f.none(days)}</p>;

  const still = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const reveal = (i: number) => {
    setSel(i);
    setOpen((o) => new Set(o).add(i));
    requestAnimationFrame(() =>
      document.getElementById(`filing-${i}`)?.scrollIntoView({ block: "nearest", behavior: still() ? "auto" : "smooth" }));
  };
  const toTimeline = (i: number) => {
    setSel(i);
    document.querySelector(".ftl")?.scrollIntoView({ block: "nearest", behavior: still() ? "auto" : "smooth" });
  };
  const toggle = (i: number) => {
    setSel(i);
    setOpen((o) => { const n = new Set(o); if (n.has(i)) n.delete(i); else n.add(i); return n; });
  };
  const reset = () => { setTag("All"); setQuery(""); };

  // Up and down move between rows, as in a terminal's news list.
  const rowKey = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    const d = e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
    if (!d) return;
    const all = [...document.querySelectorAll<HTMLButtonElement>(".filing-row")];
    const next = all[all.indexOf(e.currentTarget) + d];
    if (!next) return;
    e.preventDefault();
    next.focus();
  };

  // Rows under a heading per month, newest first (the list arrives newest first).
  const months: [string, number[]][] = [];
  shown.forEach((i) => {
    const m = filings[i].date?.slice(0, 7) ?? "";
    if (months.at(-1)?.[0] !== m) months.push([m, []]);
    months.at(-1)![1].push(i);
  });

  return (
    <>
      {end && (
        <Timeline filings={filings} shown={new Set(shown)} rows={rows} nifty={nifty} end={end} days={days}
                  sel={sel} onPoint={setSel} onPick={reveal} />
      )}
      <div className="filing-tools">
        <div className="seg seg-wrap" role="group" aria-label={f.filter}>
          <button type="button" aria-pressed={tag === "All"} onClick={() => setTag("All")}>{f.all} {filings.length}</button>
          {look > 0 && (
            <button type="button" aria-pressed={tag === LOOK} onClick={() => setTag(LOOK)}>{f.look} {look}</button>
          )}
          {tags.map(([x, n]) => (
            <button key={x} type="button" aria-pressed={tag === x} onClick={() => setTag(x)}>{f.tag[x] ?? x} {n}</button>
          ))}
        </div>
        <input type="search" className="filing-search" value={query} onChange={(e) => setQuery(e.target.value)}
               placeholder={f.search} aria-label={f.search} />
      </div>
      {shown.length === 0 ? (
        <p className="empty">{f.noMatch} <button type="button" className="linkish" onClick={reset}>{f.showAll}</button></p>
      ) : months.map(([m, list]) => (
        <section key={m} className="filing-month">
          <h3 className="filing-month-head">{m ? monthYear(`${m}-01`, lang) : ""}</h3>
          <ul className="filings">
            {list.map((i) => {
              const x = filings[i], isOpen = open.has(i);
              const a = x.date ? around(rows, nifty, x.date) : null;
              return (
                <li key={i} id={`filing-${i}`} className={`filing${sel === i ? " on" : ""}`}
                    onPointerEnter={(e) => e.pointerType === "mouse" && setSel(i)}>
                  <button type="button" className="filing-row" aria-expanded={isOpen} aria-controls={`filing-${i}-more`}
                          onClick={() => toggle(i)} onKeyDown={rowKey}>
                    <span className="filing-date">{dayMonthYear(x.date, lang)}</span>
                    <span className="filing-body">
                      <span className="filing-tag">{label(x)}{x.worth_a_look && <span className="look">{f.look}</span>}</span>
                      <span className="filing-subject" lang="en">{x.subject}</span>
                    </span>
                    <span className="filing-chev" aria-hidden>{isOpen ? "−" : "+"}</span>
                  </button>
                  <a className="filing-link" href={x.pdf_url} target="_blank" rel="noreferrer"
                     aria-label={f.openAria(label(x), dayMonthYear(x.date, lang))}>{f.open}</a>
                  <div id={`filing-${i}-more`} className="filing-more" hidden={!isOpen}>
                    <p className="filing-full" lang="en">{x.subject}</p>
                    {a ? (
                      <p>
                        {f.aroundLong(rupees(a.from[1]), dayMonthYear(a.from[0], lang), rupees(a.to[1]), dayMonthYear(a.to[0], lang))}{" "}
                        <b className={a.pct > 0 ? "up" : a.pct < 0 ? "down" : ""}>{signedPct(a.pct)}</b>
                        {a.nifty != null && <>. {f.aroundNifty(signedPct(a.nifty))}</>}
                      </p>
                    ) : x.date ? <p>{f.aroundNone}</p> : null}
                    {a && <p className="small-print">{f.aroundNote}</p>}
                    <p className="small-print" lang="en">{f.category(x.category)}</p>
                    {x.date && end && (
                      <button type="button" className="linkish" onClick={() => toTimeline(i)}>{f.showOnTimeline}</button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </>
  );
}

type TimelineProps = {
  filings: Filing[]; shown: Set<number>; rows: PriceRow[]; nifty: [string, number][] | null; end: string; days: number;
  sel: number | null; onPoint: (i: number) => void; onPick: (i: number) => void;
};

function Timeline({ filings, shown, rows, nifty, end, days, sel, onPoint, onPick }: TimelineProps) {
  const { t, lang } = useT();
  const f = t.filings;
  const t1 = ms(end), t0 = t1 - days * DAY;
  const at = (iso: string) => Math.min(1, Math.max(0, (ms(iso) - t0) / (t1 - t0)));

  // Filings by date, the ones worth a look at the bottom of each stack so they are never cut off.
  const dates = useMemo(() => {
    const by = new Map<string, number[]>();
    filings.forEach((x, i) => { if (x.date && ms(x.date) >= t0) by.set(x.date, [...(by.get(x.date) ?? []), i]); });
    by.forEach((list) => list.sort((a, b) => Number(filings[b].worth_a_look) - Number(filings[a].worth_a_look)));
    return [...by.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [filings, t0]);
  const live = dates.map(([d, list]) => [d, list.filter((i) => shown.has(i))] as const).filter(([, l]) => l.length);

  const win = rows.filter((r) => ms(r[0]) >= t0 - 3 * DAY && ms(r[0]) <= t1);
  const lo = Math.min(...win.map((r) => r[1])), hi = Math.max(...win.map((r) => r[1]));
  const y = (v: number) => (hi > lo ? (1 - (v - lo) / (hi - lo)) * 100 : 50);
  const line = win.map((r) => `${(at(r[0]) * 1000).toFixed(1)},${y(r[1]).toFixed(2)}`).join(" ");

  const months: string[] = [];
  for (let d = new Date(t0); d.getTime() <= t1; d.setUTCDate(d.getUTCDate() + 1)) {
    if (d.getUTCDate() === 1) months.push(d.toISOString().slice(0, 10));
  }

  const cur = sel != null ? filings[sel] : null;
  const curDate = cur?.date && ms(cur.date) >= t0 ? cur.date : null;
  const sameDay = curDate ? (dates.find(([d]) => d === curDate)?.[1].length ?? 1) - 1 : 0;
  const a = curDate ? around(rows, nifty, curDate) : null;
  let dot: PriceRow | null = null;
  if (curDate) for (const r of win) if (r[0] <= curDate) dot = r;

  const pointAt = (clientX: number, el: Element) => {
    const box = el.getBoundingClientRect();
    const x = (clientX - box.left) / box.width;
    let best: number | null = null, gap = Infinity;
    live.forEach(([d, list]) => { const g = Math.abs(at(d) - x); if (g < gap) { gap = g; best = list[0]; } });
    return best;
  };
  const step = (dir: number) => {
    if (!live.length) return;
    const k = curDate ? live.findIndex(([d]) => d === curDate) : -1;
    const next = k < 0 ? (dir > 0 ? 0 : live.length - 1) : Math.max(0, Math.min(live.length - 1, k + dir));
    onPoint(live[next][1][0]);
  };
  const key = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); step(e.key === "ArrowRight" ? 1 : -1); }
    else if (e.key === "Enter" && sel != null) { e.preventDefault(); onPick(sel); }
  };

  return (
    <figure className="ftl chart">
      <div className="chart-head">
        <p className="chart-read" aria-live="polite">
          {cur ? (
            <>
              <b>{dayMonthYear(cur.date, lang)}: {f.tag[cur.tag] ?? cur.tag}</b>
              {sameDay > 0 && <span className="chart-sub"> {f.more(sameDay)}</span>}
              <span className="ftl-move chart-sub">
                {a ? <>{f.aroundShort(signedPct(a.pct))}{a.nifty != null && `, ${f.niftyShort(signedPct(a.nifty))}`}</>
                  : curDate ? f.aroundNone : ""}
              </span>
            </>
          ) : <span className="chart-sub">{f.timeline(days)}</span>}
        </p>
      </div>
      <div className="chart-box">
        <svg width="100%" height={H} role="group" aria-label={f.timeline(days)} tabIndex={0} onKeyDown={key}
             onPointerMove={(e) => { if (e.pointerType !== "mouse") return; const i = pointAt(e.clientX, e.currentTarget); if (i != null) onPoint(i); }}
             onClick={(e) => { const i = pointAt(e.clientX, e.currentTarget); if (i != null) onPick(i); }}>
          {win.length > 1 && (
            <svg x="0" y={TOP} width="100%" height={LINE_H} viewBox="0 0 1000 100" preserveAspectRatio="none" overflow="visible">
              <polyline points={line} className="ftl-line" vectorEffect="non-scaling-stroke" />
            </svg>
          )}
          <line x1="0" x2="100%" y1={BASE + 0.5} y2={BASE + 0.5} stroke="var(--rule)" />
          {months.map((m) => (
            <g key={m}>
              <line x1={`${at(m) * 100}%`} x2={`${at(m) * 100}%`} y1={BASE} y2={BASE + 5} stroke="var(--rule)" />
              <text x={`${at(m) * 100}%`} y={H - 4} className="chart-tick"
                    textAnchor={at(m) > 0.96 ? "end" : at(m) < 0.04 ? "start" : "middle"}>{monthShort(m, lang)}</text>
            </g>
          ))}
          {curDate && (
            <line x1={`${at(curDate) * 100}%`} x2={`${at(curDate) * 100}%`} y1={TOP - 4} y2={BASE} className="ftl-guide" />
          )}
          {dot && <circle cx={`${at(dot[0]) * 100}%`} cy={TOP + (y(dot[1]) / 100) * LINE_H} r="3.5" className="ftl-dot" />}
          {dates.map(([d, list]) => list.slice(0, MAX_STACK).map((i, k) => (
            <rect key={i} x={`${at(d) * 100}%`} transform={`translate(${-MARK / 2},0)`} y={BASE - 3 - (k + 1) * (MARK + 2)}
                  width={MARK} height={MARK} rx="1" pointerEvents="none"
                  className={`ftl-mark${filings[i].worth_a_look ? " look" : ""}${shown.has(i) ? "" : " off"}${i === sel ? " on" : ""}`} />
          )))}
        </svg>
      </div>
      <figcaption className="chart-sub">{f.timelineSub}</figcaption>
    </figure>
  );
}
