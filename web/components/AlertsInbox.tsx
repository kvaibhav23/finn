"use client";

import Link from "next/link";
import { useMemo } from "react";

import { crisp, dayMonthYear, dayTime, signedPct } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import { DEFAULT_RULES, RULE_LIMITS, useRules, useSeen, useTypes } from "@/lib/prefs";
import type { DigestItem } from "@/lib/types";
import { moveAlerts, type MoveAlert, type Session } from "@/lib/watch";

export interface Watched { symbol: string; name: string; rows: Session[] }

type Alert = MoveAlert | { kind: "filing"; symbol: string; date: string; item: DigestItem };

/** The reader's own rules, run against the watched companies' recent sessions and filings. */
export function AlertsInbox({ companies, filings }: { companies: Watched[]; filings: DigestItem[] }) {
  const { t, lang } = useT();
  const a = t.inbox;
  const [rules, setRules] = useRules();
  const [types] = useTypes();
  const [seen, setSeen] = useSeen();

  const first = companies.flatMap((c) => c.rows.slice(-20, -19).map((r) => r[0])).sort()[0] ?? "";
  const byDay = useMemo(() => {
    const m = new Map<string, DigestItem[]>();
    for (const f of filings) {
      const k = `${f.symbol}${f.filed_at.slice(0, 10)}`;
      m.set(k, [...(m.get(k) ?? []), f]);
    }
    return m;
  }, [filings]);

  const alerts: Alert[] = [
    ...companies.flatMap((c) => moveAlerts(c.symbol, c.rows, rules)),
    // Filing alerts: the types the reader chose (shared with the digest), else the ones the digest puts first.
    ...filings.filter((f) => f.filed_at.slice(0, 10) >= first && (types ? types.includes(f.tag) : f.priority === 1))
      .map((item) => ({ kind: "filing" as const, symbol: item.symbol, date: item.filed_at, item })),
  ].sort((x, y) => y.date.localeCompare(x.date));
  // Never marked as read: only the latest day counts as new, not the whole month.
  const latest = alerts[0]?.date.slice(0, 10) ?? "";
  const isNew = (x: Alert) => seen ? x.date.slice(0, 16) > seen.slice(0, 16) : x.date.slice(0, 10) === latest;
  const days = [...new Set(alerts.map((x) => x.date.slice(0, 10)))];
  const fresh = alerts.filter(isNew).length;
  const names = Object.fromEntries(companies.map((c) => [c.symbol, c.name]));

  const num = (key: "price" | "volume", label: string, unit: string) => {
    const lim = RULE_LIMITS[key];
    return (
      <label className="rule">
        <span>{label}</span>
        <span className="rule-input">
          {key === "price" && <span aria-hidden>±</span>}
          <input type="number" inputMode="decimal" min={lim.min} max={lim.max} step={lim.step} value={rules[key]}
                 onChange={(e) => { const v = Number(e.target.value); if (Number.isFinite(v) && v > 0) setRules({ ...rules, [key]: v }); }} />
          <span>{unit}</span>
        </span>
      </label>
    );
  };

  return (
    <>
      <section className="rules" aria-labelledby="rules-title">
        <h2 className="sub-title" id="rules-title">{a.rules}</h2>
        <div className="rules-grid">
          {num("price", a.price, "%")}
          {num("volume", a.volume, a.volumeUnit)}
          <p className="rule rule-link">
            <span>{a.filings}</span>
            <Link href="/digest">{types ? types.map((x) => t.filings.tag[x] ?? x).join(", ") : t.digest.high}</Link>
          </p>
        </div>
        <p className="small-print">
          {a.saved}.{" "}
          {(rules.price !== DEFAULT_RULES.price || rules.volume !== DEFAULT_RULES.volume) && (
            <button type="button" className="btn-plain" onClick={() => setRules(null)}>{a.reset}</button>
          )}
        </p>
      </section>

      <div className="inbox-head">
        <p className="dg-count" aria-live="polite">
          {a.count(alerts.length)}{fresh > 0 && <span className="inbox-new"> {a.newCount(fresh)}</span>}
        </p>
        {fresh > 0 && (
          <button type="button" className="btn-quiet" onClick={() => setSeen(new Date().toISOString())}>{a.markRead}</button>
        )}
      </div>

      {alerts.length === 0 ? <p className="empty">{a.none}</p> : (
        <div className="inbox">
          {days.map((day) => (
            <section key={day} className="inbox-day" aria-label={dayMonthYear(day, lang)}>
              <h3 className="inbox-date">{dayMonthYear(day, lang)}</h3>
              <ol>
          {alerts.filter((x) => x.date.slice(0, 10) === day).map((x) => {
            const sameDay = x.kind === "move" ? byDay.get(`${x.symbol}${x.date}`) ?? [] : [];
            return (
              <li key={`${x.kind}${x.symbol}${x.date}${x.kind === "filing" ? x.item.pdf_url : ""}`}
                  className={`inbox-item${isNew(x) ? " new" : ""}${x.kind === "move" ? (x.price ? (x.pct >= 0 ? " up" : " down") : " vol") : " f-item"}`}>
                <div className="dg-meta">
                  {x.kind === "filing" && <time dateTime={x.date}>{dayTime(x.date, lang).split(", ").at(-1)}</time>}
                  <Link href={`/c/${x.symbol}${x.kind === "move" ? "#price" : "#filings"}`} className="feed-sym">{x.symbol}</Link>
                  {isNew(x) && <span className="inbox-dot">{a.unread}</span>}
                </div>
                {x.kind === "move" ? (
                  <div className="inbox-body">
                    <p className="inbox-line">
                      <b className={x.price ? (x.pct >= 0 ? "up" : "down") : undefined}>
                        {x.price || x.volumeX == null
                          ? (x.pct >= 0 ? a.rose : a.fell)(signedPct(x.pct), dayMonthYear(x.date, lang))
                          : a.volumeOnly(x.volumeX.toFixed(1), dayMonthYear(x.date, lang))}
                      </b>
                      {x.price && x.volumeX != null && <span className="inbox-vol">, {a.volumeX(x.volumeX.toFixed(1))}</span>}
                      <span className="inbox-name"> {names[x.symbol]}</span>
                    </p>
                    {sameDay.length > 0 && (
                      <p className="small-print">
                        {a.thatDay}{" "}
                        {sameDay.map((f, i) => (
                          <span key={f.pdf_url}>{i > 0 && "; "}<a href={f.pdf_url} target="_blank" rel="noreferrer">{t.filings.tag[f.tag] ?? f.tag}</a></span>
                        ))}
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="inbox-body">
                    <p className="inbox-line"><span className="dg-tag">{t.filings.tag[x.item.tag] ?? x.item.tag}</span> <span className="inbox-name">{names[x.symbol] ?? x.item.name}</span></p>
                    <a className="dg-text" href={x.item.pdf_url} target="_blank" rel="noreferrer" lang="en">{crisp(x.item.subject)}</a>
                  </div>
                )}
              </li>
            );
          })}
              </ol>
            </section>
          ))}
        </div>
      )}
      <p className="small-print">{a.delivery}</p>
    </>
  );
}
