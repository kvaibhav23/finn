"use client";

import { useEffect, useMemo, useState } from "react";

import { monthYear, pageLink, quarter } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { Dict, Lang } from "@/lib/i18n";
import { VERDICTS, type Ledger, type Promise_, type Verdict } from "@/lib/types";
import { GROUPS } from "@/lib/verdicts";

import { Track, domainFor, type Domain } from "./Track";
import { VerdictMark, verdictClass } from "./VerdictMark";

export function LedgerView({ ledger }: { ledger: Ledger }) {
  const { t, lang } = useT();
  const [verdict, setVerdict] = useState<Verdict | "All">("All");
  const [metric, setMetric] = useState("All");
  const [made, setMade] = useState("All");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [showUnverifiable, setShowUnverifiable] = useState(false);

  const counts = useMemo(() => {
    const c = Object.fromEntries(VERDICTS.map((v) => [v, 0])) as Record<Verdict, number>;
    ledger.promises.forEach((p) => { c[p.verdict] += 1; });
    return c;
  }, [ledger]);
  const metrics = useMemo(() => [...new Set(ledger.promises.map((p) => p.metric))].sort(), [ledger]);
  const domain = useMemo(() => domainFor(ledger.promises, ledger.calls), [ledger]);
  const matching = ledger.promises.filter((p) =>
    (verdict === "All" || p.verdict === verdict) && (metric === "All" || p.metric === metric)
    && (made === "All" || p.first_quarter === made));
  // Promises nothing could check are kept out of the way under "All": they bury the ones with an answer.
  const hidden = verdict === "All" && !showUnverifiable ? matching.filter((p) => p.verdict === "Unverifiable").length : 0;
  const shown = hidden ? matching.filter((p) => p.verdict !== "Unverifiable") : matching;

  // A tap on an earnings call in the price chart shows the promises first made on that call.
  useEffect(() => {
    const onMade = (e: Event) => {
      const q = (e as CustomEvent<string>).detail;
      if (ledger.calls.some((c) => c.quarter === q)) { setMade(q); setVerdict("All"); setMetric("All"); }
    };
    window.addEventListener("finn:made", onMade);
    return () => window.removeEventListener("finn:made", onMade);
  }, [ledger]);

  // /c/SYMBOL#<promise id> opens that promise: a shareable link to one receipt (also from "Coming up").
  useEffect(() => {
    const openHash = () => {
      const id = decodeURIComponent(window.location.hash.slice(1));
      const target = ledger.promises.find((p) => p.id === id);
      if (!id || !target) return;
      if (target.verdict === "Unverifiable") setShowUnverifiable(true);
      setVerdict("All"); setMetric("All"); setMade("All");
      setOpen((s) => new Set([...s, id]));
      requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: "start" }));
    };
    openHash();
    window.addEventListener("hashchange", openHash);
    return () => window.removeEventListener("hashchange", openHash);
  }, [ledger]);

  const toggle = (id: string) => setOpen((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <>
      <div className="tally" role="group" aria-label={t.ledger.filterVerdict}>
        <button type="button" aria-pressed={verdict === "All"} onClick={() => setVerdict("All")}>
          {t.ledger.all} <span className="n">{ledger.promises.length}</span>
        </button>
        {GROUPS.map((g) => (
          <span key={g.key} className="tally-group">
            <span className="tally-label">{t.groups[g.key]}</span>
            {g.verdicts.map((v) => (
              <button key={v} type="button" aria-pressed={verdict === v} disabled={!counts[v]}
                      onClick={() => setVerdict(verdict === v ? "All" : v)}>
                <VerdictMark verdict={v} /> {t.verdict[v]} <span className="n">{counts[v]}</span>
              </button>
            ))}
          </span>
        ))}
      </div>
      {verdict !== "All" && <p className="meaning"><b>{t.verdict[verdict]}:</b> {t.meaning[verdict]}</p>}

      <div className="filters">
        <label>{t.ledger.metric}
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="All">{t.ledger.all}</option>
            {metrics.map((m) => <option key={m} value={m}>{t.metric[m] ?? m}</option>)}
          </select>
        </label>
        <label>{t.ledger.firstSaid}
          <select value={made} onChange={(e) => setMade(e.target.value)}>
            <option value="All">{t.ledger.anyCall}</option>
            {ledger.calls.map((c) => <option key={c.quarter} value={c.quarter}>{quarter(c.quarter)}</option>)}
          </select>
        </label>
        {made !== "All" && (
          <button type="button" className="btn-plain" onClick={() => setMade("All")}>{t.ledger.everyCall}</button>
        )}
        <span className="count" aria-live="polite">{t.ledger.count(shown.length, ledger.promises.length)}</span>
      </div>

      {shown.length === 0 ? (
        <p className="empty">{hidden ? t.ledger.allUnverifiable : t.ledger.none}</p>
      ) : (
        <ul className="rows">
          {shown.map((p) => (
            <Row key={p.id} p={p} ledger={ledger} domain={domain} open={open.has(p.id)} onToggle={() => toggle(p.id)}
                 t={t} lang={lang} />
          ))}
        </ul>
      )}
      {(hidden > 0 || (showUnverifiable && verdict === "All")) && (
        <p className="unverified">
          {hidden > 0 ? `${t.ledger.hidden(hidden)} ` : `${t.ledger.showing} `}
          <button type="button" className="btn-plain" onClick={() => setShowUnverifiable(!showUnverifiable)}>
            {hidden > 0 ? t.ledger.show : t.ledger.hide}
          </button>
        </p>
      )}
    </>
  );
}

function Row({ p, ledger, domain, open, onToggle, t, lang }:
  { p: Promise_; ledger: Ledger; domain: Domain; open: boolean; onToggle: () => void; t: Dict; lang: Lang }) {
  const detailId = `d-${p.id}`;
  const due = p.due ? `${t.ledger.due(monthYear(p.due, lang))}${p.due_assumed ? t.ledger.dueAssumed : ""}` : t.ledger.noDeadline;
  const actual = p.actual?.text ? `${t.ledger.actualText[p.actual.text] ?? p.actual.text}${p.actual.partial ? t.ledger.soFar : ""}` : null;
  return (
    <li className="row" id={p.id}>
      <button type="button" className="row-btn" aria-expanded={open} aria-controls={detailId} onClick={onToggle}>
        <span>
          <span className="row-title" lang="en">{p.title}</span>
          <span className="row-sub" style={{ display: "block" }}>
            {t.ledger.firstSaidIn(quarter(p.first_quarter))}, {due}
            {p.conditional && <span className="cond">{t.ledger.conditional}</span>}
          </span>
        </span>
        <span className="row-track"><Track p={p} calls={ledger.calls} asOf={ledger.as_of_results} domain={domain} t={t} lang={lang} /></span>
        <span className="row-out">
          <span className={`row-verdict ${verdictClass(p.verdict)}`}><VerdictMark verdict={p.verdict} /> {t.verdict[p.verdict]}</span>
          {actual && <span className="row-actual">{actual}</span>}
        </span>
      </button>
      <div className="detail" id={detailId} hidden={!open}>
        <div>
          <blockquote className="quote" lang="en">“{p.quote}”</blockquote>
          <p className="cite">
            {t.ledger.cite(p.speaker, quarter(p.quarter), p.page)}{" "}
            {pageLink(p.pdf_url, p.page) && <a href={pageLink(p.pdf_url, p.page)!} target="_blank" rel="noreferrer">{t.ledger.openTranscript}</a>}
            <a href={`#${p.id}`} style={{ marginLeft: 14 }}>{t.ledger.link}</a>
          </p>
          {p.history.length > 1 && (
            <ol className="history" aria-label={t.ledger.everyTime}>
              {p.history.map((v, i) => (
                <li key={i}>
                  <span className="h-q">{quarter(v.quarter)}</span>
                  <span className="h-s">{t.ledger.status[v.status] ?? v.status}{v.status === "Revised" ? t.ledger.revisedTo(v.target) : ""}</span>
                  <span className="h-quote" lang="en">
                    “{v.quote}”{" "}
                    {pageLink(v.pdf_url, v.page) && (
                      <a href={pageLink(v.pdf_url, v.page)!} target="_blank" rel="noreferrer"
                         style={{ fontFamily: "var(--font-ui)", fontStyle: "normal", fontSize: "var(--s13)" }}>
                        {t.ledger.page(v.page)}
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
            <h4>{t.ledger.target}</h4>
            <p>{p.target !== "—" ? p.target : (t.metric[p.metric] ?? p.metric_label)}{p.scope === "segment" ? t.ledger.partOfBusiness : ""}</p>
          </div>
          <Actual p={p} t={t} />
          <div className="fact">
            <h4>{t.ledger.why(t.verdict[p.verdict])}</h4>
            <p lang="en">{p.explanation}</p>
            {p.verdict === "Dropped" && p.searched_later.length > 0 && (
              <p className="small">{t.ledger.notAgain(p.searched_later.map(quarter).join(", "))}</p>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function Actual({ p, t }: { p: Promise_; t: Dict }) {
  const a = p.actual;
  if (!a) {
    return (
      <div className="fact">
        <h4>{t.ledger.actual}</h4>
        <p className="small">{t.ledger.noActual}</p>
      </div>
    );
  }
  if (a.source === "XBRL filing") {
    return (
      <div className="fact">
        <h4>{t.ledger.actual}{a.partial ? t.ledger.ytd : ""}</h4>
        <p>{a.text}{a.basis ? `, ${a.basis}` : ""}{a.definition ? `, ${a.definition}` : ""}</p>
        <p className="small">
          {t.ledger.computed}{" "}
          {a.link && <a href={a.link} target="_blank" rel="noreferrer">{t.ledger.xbrl}</a>}
        </p>
        {a.note && <p className="small" lang="en">{t.ledger.definition(a.note)}</p>}
      </div>
    );
  }
  return (
    <div className="fact">
      <h4>{t.ledger.byManagement}</h4>
      <p>{a.text ? t.ledger.actualText[a.text] ?? a.text : ""}</p>
      {a.quote && (
        <p className="small">
          <span lang="en">“{a.quote}”</span> {t.ledger.later(a.speaker ?? "", quarter(a.quarter), a.page ?? 1)}{" "}
          {pageLink(a.pdf_url ?? null, a.page ?? 1) && (
            <a href={pageLink(a.pdf_url ?? null, a.page ?? 1)!} target="_blank" rel="noreferrer">{t.ledger.openTranscript}</a>
          )}
        </p>
      )}
    </div>
  );
}
