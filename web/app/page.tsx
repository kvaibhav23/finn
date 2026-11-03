import Link from "next/link";

import { AreaChart } from "@/components/AreaChart";
import { Feed, type FeedItem } from "@/components/Feed";
import { MarketBanner } from "@/components/MarketBanner";
import { Monitor, type MonitorRow } from "@/components/Monitor";
import { Search } from "@/components/Search";
import { Track } from "@/components/Track";
import { VerdictMark, verdictClass } from "@/components/VerdictMark";
import { ms, periodReturns } from "@/lib/chart";
import { getIndex, getLedger, getMarket, getMarketDay } from "@/lib/data";
import { dayMonthYear, displayName, monthYear, quarter, rupees, signedPct } from "@/lib/format";
import { getT } from "@/lib/i18n/server";
import { moveTitle } from "@/lib/sentences";
import type { Ledger } from "@/lib/types";

export const dynamic = "force-dynamic";

const FEED_DAYS = 30;
const DAY = 86_400_000;
const OPEN = new Set(["On track", "Pending", "Revised"]);
const FEED_TAGS: Record<string, FeedItem["kind"]> = {
  Results: "results", "Order or contract": "order", "Dividend or corporate action": "dividend",
};

/** "Tata Consultancy Services Limited has informed the Exchange regarding 'X'." -> "X" (NSE's own boilerplate). */
function crisp(subject: string): string {
  const s = subject.replace(/^.*?has informed the Exchange (?:about|regarding|that)\s*/i, "").replace(/^['‘"]|['’".]+$/g, "").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : subject;
}

export default async function Home() {
  const [{ t, lang }, index, day] = await Promise.all([getT(), getIndex(), getMarketDay()]);
  const ready = index.filter((i) => i.status === "ok");
  const [markets, ledgers] = await Promise.all([
    Promise.all(ready.map((e) => getMarket(e.symbol))),
    Promise.all(ready.map((e) => getLedger(e.symbol))),
  ]);
  const h = t.home;
  const today = day?.date ?? ready.find((e) => e.price_as_of)?.price_as_of ?? new Date().toISOString().slice(0, 10);

  const rows: MonitorRow[] = ready.map((e, i) => {
    const m = markets[i];
    const prices = m?.prices?.rows ?? [];
    return {
      symbol: e.symbol, name: displayName(e.name, e.symbol), close: e.close ?? null, day: e.change_pct ?? null,
      m1: periodReturns(prices, null).find((r) => r.key === "1M")?.stock ?? null, y1: e.return_1y ?? null,
      spark: e.spark ?? [], pe: m?.results?.pe ?? null, cap: m?.results?.market_cap_cr ?? null,
      kept: e.counts.Kept, decided: e.counts.Kept + e.counts.Missed,
      look: m?.filings ? m.filings.filter((f) => f.worth_a_look).length : null,
    };
  });

  const feed: FeedItem[] = [];
  ready.forEach((e, i) => {
    const m = markets[i];
    if (!m) return;
    if (m.move && ms(m.move.date) >= ms(today) - FEED_DAYS * DAY) {
      feed.push({ date: m.move.date, symbol: e.symbol, kind: "move", tag: t.companies.bigMove,
        text: moveTitle(t, lang, m.move), href: `/c/${e.symbol}#price`, english: false,
        tone: m.move.change_pct >= 0 ? "up" : "down" });
    }
    const seen = new Set<string>();   // one item per company, kind and day: a board meeting often files three notices
    for (const f of m.filings ?? []) {
      if (!f.date || ms(f.date) < ms(today) - FEED_DAYS * DAY) continue;
      const kind = f.worth_a_look ? "look" : FEED_TAGS[f.tag];
      if (!kind || seen.has(`${kind}${f.date}`)) continue;
      seen.add(`${kind}${f.date}`);
      feed.push({ date: f.date, symbol: e.symbol, kind, tag: t.filings.tag[f.tag] ?? f.tag, text: crisp(f.subject),
        href: f.pdf_url, english: true, tone: null });
    }
  });
  feed.sort((a, b) => b.date.localeCompare(a.date) || (a.kind === "move" ? -1 : 1));

  // The soonest stated deadlines, at most two per company so one company can't fill the list.
  const due = ledgers.flatMap((l) => l?.status === "ok"
    ? l.promises.filter((p) => OPEN.has(p.verdict) && p.due && !p.due_assumed && ms(p.due) >= ms(today))
      .sort((a, b) => a.due!.localeCompare(b.due!)).slice(0, 2).map((p) => ({ l, p })) : [])
    .sort((a, b) => a.p.due!.localeCompare(b.p.due!)).slice(0, 6);

  const ex = example(ledgers);
  const nifty = markets.find((m) => m?.nifty?.length)?.nifty ?? null;
  const niftyReturns = nifty ? periodReturns(nifty, null).filter((r) => r.key !== "1W") : [];

  return (
    <>
      <Ticker day={day} entries={ready} label={h.tickerAria} />
      {day && <MarketBanner day={day} t={t} lang={lang} />}

      <section className="hero">
        <div className="hero-text">
          <h1>{h.title}</h1>
          <p className="lede">{h.lede}</p>
          <Search analysed={index.map((i) => i.symbol)} autoFocus />
          <ul className="hero-sources">
            {h.sources.map((s) => <li key={s}>{s}</li>)}
          </ul>
        </div>
        {day && nifty && (
          <aside className="nifty" aria-label={h.nifty.title}>
            <p className="nifty-name">{h.nifty.title}</p>
            <p className="nifty-quote">
              <span className="nifty-last">{day.close.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              <span className={`pill ${day.change_pct >= 0 ? "up" : "down"}`}>{signedPct(day.change_pct, 2)}</span>
            </p>
            <p className="chart-sub">{h.nifty.close(dayMonthYear(day.date, lang))}</p>
            <AreaChart series={nifty} label={h.nifty.title} />
            <ul className="nifty-returns">
              {niftyReturns.map((r) => (
                <li key={r.key}>
                  <span>{t.view.returns.label[r.key]}</span>
                  <b className={r.stock >= 0 ? "up" : "down"}>{signedPct(r.stock)}</b>
                </li>
              ))}
            </ul>
            <p className="small-print">{h.nifty.hint}</p>
          </aside>
        )}
      </section>

      {rows.length > 0 && (
        <section className="home-block" aria-labelledby="monitor-title">
          <h2 className="section-title" id="monitor-title">{h.monitor.title}</h2>
          <p className="section-sub">{h.monitor.sub}</p>
          <Monitor rows={rows} />
          <p className="small-print"><Link href="/companies">{h.allCompanies}</Link></p>
        </section>
      )}

      <div className="home-pair">
        <Feed items={feed} days={FEED_DAYS} />
        {due.length > 0 && (
          <section className="home-due" aria-labelledby="due-title">
            <h2 className="section-title" id="due-title">{h.coming.title}</h2>
            <p className="section-sub">{h.coming.sub}</p>
            <ol className="due-list">
              {due.map(({ l, p }) => (
                <li key={p.id}>
                  <Link href={`/c/${l.symbol}#${p.id}`}>
                    <span className="due-when">{t.view.coming.due(monthYear(p.due, lang))}</span>
                    <span className="feed-sym">{l.symbol}</span>
                    <span className="due-what" lang="en">{p.title}</span>
                    <span className={`coming-v ${verdictClass(p.verdict)}`}><VerdictMark verdict={p.verdict} /> {t.verdict[p.verdict]}</span>
                  </Link>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>

      {ex && (
        <section className="home-block" aria-label={h.exampleAria}>
          <h2 className="section-title">{h.exampleTitle}</h2>
          <p className="section-sub">{h.exampleSub}</p>
          <div className="example">
            <div className="example-grid">
              <div>
                <p className="example-who">
                  {h.exampleWho(displayName(ex.ledger.name, ex.ledger.symbol), ex.p.speaker, quarter(ex.p.quarter))}
                </p>
                <blockquote className="quote" lang="en">“{ex.p.quote}”</blockquote>
              </div>
              <div className="example-out">
                <Track p={ex.p} calls={ex.ledger.calls} asOf={ex.ledger.as_of_results} t={t} lang={lang} />
                <p className="example-line">
                  <span className="row-verdict v-kept" style={{ justifyContent: "flex-start" }}>
                    <VerdictMark verdict="Kept" /> {t.verdict.Kept}
                  </span>{" "}
                  <span lang="en">{ex.p.title}</span>, {h.cameIn} <strong>{ex.p.actual!.text}</strong>{" "}
                  {h.forPeriod(monthYear(ex.p.due, lang))}
                </p>
                <Link href={`/c/${ex.ledger.symbol}#promises`}>{h.seeAll(ex.ledger.promises.length)}</Link>
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="how" aria-label={t.nav.method}>
        {h.how.map((x, i) => (
          <div key={x.h} className={`how-${i}`}>
            <h3>{x.h}</h3>
            <p>{x.p}{i === 2 && <> <Link href="/method">{t.nav.method}</Link></>}</p>
          </div>
        ))}
      </section>
    </>
  );
}

/** A real promise for the example: a Kept one with a filed (XBRL) actual, repeated across calls. */
function example(ledgers: (Ledger | null)[]) {
  for (const ledger of ledgers) {
    const p = ledger?.status === "ok" ? ledger.promises
      .filter((x) => x.verdict === "Kept" && x.actual?.source === "XBRL filing" && !x.actual.partial)
      .sort((a, b) => b.history.length - a.history.length)[0] : undefined;
    if (ledger && p) return { ledger, p };
  }
  return null;
}

/** The last close of the Nifty 50 and of every company FINN covers, in one strip. */
function Ticker({ day, entries, label }:
  { day: Awaited<ReturnType<typeof getMarketDay>>; entries: Awaited<ReturnType<typeof getIndex>>; label: string }) {
  const items = entries.filter((e) => e.close != null);
  if (!day && !items.length) return null;
  const chg = (n: number | null | undefined) => n == null ? null
    : <span className={n > 0 ? "up" : n < 0 ? "down" : ""}>{n > 0 ? "▲" : n < 0 ? "▼" : ""} {signedPct(n, 2)}</span>;
  return (
    <ul className="ticker" aria-label={label}>
      {day && (
        <li className="ticker-index">
          <b>NIFTY 50</b> {day.close.toLocaleString("en-IN", { maximumFractionDigits: 2 })} {chg(day.change_pct)}
        </li>
      )}
      {items.map((e) => (
        <li key={e.symbol}>
          <Link href={`/c/${e.symbol}`}><b>{e.symbol}</b> {rupees(e.close!)} {chg(e.change_pct)}</Link>
        </li>
      ))}
    </ul>
  );
}

