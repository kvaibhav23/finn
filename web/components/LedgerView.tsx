"use client";

import { useEffect, useMemo, useState } from "react";

import { monthYear, pageLink, quarter } from "@/lib/format";
import { VERDICTS, type Ledger, type Promise_, type Verdict } from "@/lib/types";

import { Track, domainFor, type Domain } from "./Track";
import { VerdictMark, verdictClass } from "./VerdictMark";

export function LedgerView({ ledger }: { ledger: Ledger }) {
  const [verdict, setVerdict] = useState<Verdict | "All">("All");
  const [metric, setMetric] = useState("All");
  const [made, setMade] = useState("All");
  const [open, setOpen] = useState<Set<string>>(new Set());

  const counts = useMemo(() => {
    const c = Object.fromEntries(VERDICTS.map((v) => [v, 0])) as Record<Verdict, number>;
    ledger.promises.forEach((p) => { c[p.verdict] += 1; });
    return c;
  }, [ledger]);
  const metrics = useMemo(() => [...new Set(ledger.promises.map((p) => p.metric_label))].sort(), [ledger]);
  const domain = useMemo(() => domainFor(ledger.promises, ledger.calls), [ledger]);
  const shown = ledger.promises.filter((p) =>
    (verdict === "All" || p.verdict === verdict) && (metric === "All" || p.metric_label === metric)
    && (made === "All" || p.first_quarter === made));

  // /c/SYMBOL#<promise id> opens that promise: a shareable link to one receipt.
  useEffect(() => {
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (!id || !ledger.promises.some((p) => p.id === id)) return;
    setOpen(new Set([id]));
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: "start" }));
  }, [ledger]);

  const toggle = (id: string) => setOpen((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <>
      <div className="tally" role="group" aria-label="Filter by verdict">
        <button type="button" aria-pressed={verdict === "All"} onClick={() => setVerdict("All")}>
          All <span className="n">{ledger.promises.length}</span>
        </button>
        {VERDICTS.map((v) => (
          <button key={v} type="button" aria-pressed={verdict === v} disabled={!counts[v]}
                  onClick={() => setVerdict(verdict === v ? "All" : v)}>
            <VerdictMark verdict={v} /> {v} <span className="n">{counts[v]}</span>
          </button>
        ))}
      </div>

      <div className="filters">
        <label>Metric
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option>All</option>
            {metrics.map((m) => <option key={m}>{m}</option>)}
          </select>
        </label>
        <label>First said in
          <select value={made} onChange={(e) => setMade(e.target.value)}>
            <option value="All">Any call</option>
            {ledger.calls.map((c) => <option key={c.quarter} value={c.quarter}>{quarter(c.quarter)}</option>)}
          </select>
        </label>
        <span className="count" aria-live="polite">{shown.length} of {ledger.promises.length} promises</span>
      </div>

      {shown.length === 0 ? (
        <p className="empty">No promises match these filters.</p>
      ) : (
        <ul className="rows">
          {shown.map((p) => (
            <Row key={p.id} p={p} ledger={ledger} domain={domain} open={open.has(p.id)} onToggle={() => toggle(p.id)} />
          ))}
        </ul>
      )}
    </>
  );
}

function Row({ p, ledger, domain, open, onToggle }:
  { p: Promise_; ledger: Ledger; domain: Domain; open: boolean; onToggle: () => void }) {
  const detailId = `d-${p.id}`;
  const due = p.due ? `due ${monthYear(p.due)}${p.due_assumed ? " (no date stated; year end assumed)" : ""}` : "no deadline stated";
  const actual = p.actual?.text ? `${p.actual.text}${p.actual.partial ? " so far" : ""}` : null;
  return (
    <li className="row" id={p.id}>
      <button type="button" className="row-btn" aria-expanded={open} aria-controls={detailId} onClick={onToggle}>
        <span>
          <span className="row-title">{p.title}</span>
          <span className="row-sub" style={{ display: "block" }}>
            First said in {quarter(p.first_quarter)}, {due}
            {p.conditional && <span className="cond">. Conditional</span>}
          </span>
        </span>
        <span className="row-track"><Track p={p} calls={ledger.calls} asOf={ledger.as_of_results} domain={domain} /></span>
        <span className="row-out">
          <span className={`row-verdict ${verdictClass(p.verdict)}`}><VerdictMark verdict={p.verdict} /> {p.verdict}</span>
          {actual && <span className="row-actual">{actual}</span>}
        </span>
      </button>
      <div className="detail" id={detailId} hidden={!open}>
        <div>
          <blockquote className="quote">“{p.quote}”</blockquote>
          <p className="cite">
            {p.speaker}, {quarter(p.quarter)} earnings call, page {p.page}.{" "}
            {pageLink(p.pdf_url, p.page) && <a href={pageLink(p.pdf_url, p.page)!} target="_blank" rel="noreferrer">Open transcript</a>}
            <a href={`#${p.id}`} style={{ marginLeft: 14 }}>Link to this promise</a>
          </p>
          {p.history.length > 1 && (
            <ol className="history" aria-label="Every time this was said">
              {p.history.map((v, i) => (
                <li key={i}>
                  <span className="h-q">{quarter(v.quarter)}</span>
                  <span className="h-s">{v.status === "New" ? "Said" : v.status}{v.status === "Revised" ? ` to ${v.target}` : ""}</span>
                  <span className="h-quote">
                    “{v.quote}”{" "}
                    {pageLink(v.pdf_url, v.page) && (
                      <a href={pageLink(v.pdf_url, v.page)!} target="_blank" rel="noreferrer"
                         style={{ fontFamily: "var(--font-ui)", fontStyle: "normal", fontSize: "var(--s13)" }}>
                        page {v.page}
                      </a>
                    )}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
        <div className="facts">
          <div className="fact">
            <h4>Target</h4>
            <p>{p.target !== "—" ? p.target : p.metric_label}{p.scope === "segment" ? ", for part of the business" : ""}</p>
          </div>
          <Actual p={p} />
          <div className="fact">
            <h4>Why {p.verdict.toLowerCase()}</h4>
            <p>{p.explanation}</p>
            {p.verdict === "Dropped" && p.searched_later.length > 0 && (
              <p className="small">Not mentioned again in {p.searched_later.map(quarter).join(", ")}.</p>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function Actual({ p }: { p: Promise_ }) {
  const a = p.actual;
  if (!a) {
    return (
      <div className="fact">
        <h4>Actual</h4>
        <p className="small">No filed figure or later statement by management was found.</p>
      </div>
    );
  }
  if (a.source === "XBRL filing") {
    return (
      <div className="fact">
        <h4>Actual{a.partial ? ", year to date" : ""}</h4>
        <p>{a.text}{a.basis ? `, ${a.basis}` : ""}{a.definition ? `, ${a.definition}` : ""}</p>
        <p className="small">
          Computed from the company&apos;s filed results.{" "}
          {a.link && <a href={a.link} target="_blank" rel="noreferrer">XBRL filing</a>}
        </p>
        {a.note && <p className="small">Definition: {a.note}</p>}
      </div>
    );
  }
  return (
    <div className="fact">
      <h4>Actual, as reported by management</h4>
      <p>{a.text}</p>
      {a.quote && (
        <p className="small">
          “{a.quote}” {a.speaker}, {quarter(a.quarter)} call, page {a.page}.{" "}
          {pageLink(a.pdf_url ?? null, a.page ?? 1) && (
            <a href={pageLink(a.pdf_url ?? null, a.page ?? 1)!} target="_blank" rel="noreferrer">Open transcript</a>
          )}
        </p>
      )}
    </div>
  );
}
