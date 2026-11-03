import Link from "next/link";

import { MarketBanner } from "@/components/MarketBanner";
import { Search } from "@/components/Search";
import { Sparkline } from "@/components/Sparkline";
import { Track } from "@/components/Track";
import { VerdictMark } from "@/components/VerdictMark";
import { getIndex, getLedger, getMarketDay } from "@/lib/data";
import { displayName, monthYear, quarter, rupees, signedPct } from "@/lib/format";
import { getT } from "@/lib/i18n/server";
import type { IndexEntry, Ledger, Promise_ } from "@/lib/types";

export const dynamic = "force-dynamic";

/** A real promise for the opening example: a Kept one with a filed (XBRL) actual, repeated across calls. */
async function example(index: IndexEntry[]): Promise<{ ledger: Ledger; p: Promise_ } | null> {
  for (const e of index.filter((i) => i.status === "ok")) {
    const ledger = await getLedger(e.symbol);
    const p = ledger?.promises
      .filter((x) => x.verdict === "Kept" && x.actual?.source === "XBRL filing" && !x.actual.partial)
      .sort((a, b) => b.history.length - a.history.length)[0];
    if (ledger && p) return { ledger, p };
  }
  return null;
}

function Mix({ c, total }: { c: IndexEntry["counts"]; total: number }) {
  if (!total) return null;
  const w = (n: number) => `${(n / total) * 100}%`;
  return (
    <span className="mix" aria-hidden>
      <span className="kept" style={{ width: w(c.Kept) }} />
      <span className="missed" style={{ width: w(c.Missed) }} />
      <span className="open" style={{ width: w(c["On track"] + c.Revised) }} />
    </span>
  );
}

export default async function Home() {
  const [{ t, lang }, index, day] = await Promise.all([getT(), getIndex(), getMarketDay()]);
  const ex = await example(index);
  const ready = index.filter((i) => i.status === "ok");
  const h = t.home;

  return (
    <>
      {day && <MarketBanner day={day} t={t} lang={lang} />}
      <section className="home-hero">
        <h1>{h.title}</h1>
        <p className="lede">{h.lede}</p>
        <Search analysed={index.map((i) => i.symbol)} autoFocus />
      </section>

      {ex && (
        <section className="example" aria-label={h.exampleAria}>
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
              <Link href={`/c/${ex.ledger.symbol}`}>{h.seeAll(ex.ledger.promises.length)}</Link>
            </div>
          </div>
        </section>
      )}

      <section aria-labelledby="ready-title">
        <h2 className="section-title" id="ready-title">{h.readyTitle}</h2>
        <p className="section-sub">{h.readySub}</p>
        <ul className="co-list">
          {ready.map((e) => {
            const decided = e.counts.Kept + e.counts.Missed;
            return (
              <li key={e.symbol}>
                <Link href={`/c/${e.symbol}`} className="co-row">
                  <span className="co-name">
                    {displayName(e.name, e.symbol)}<span className="co-sym">{e.symbol}</span>
                    {e.close != null && (
                      <span className="co-price">
                        <b>{rupees(e.close)}</b>{" "}
                        {e.change_pct != null && (
                          <span className={e.change_pct > 0 ? "up" : e.change_pct < 0 ? "down" : ""}>
                            {signedPct(e.change_pct, 2)}
                          </span>
                        )}
                        {e.big_move && <span className="look">{t.companies.bigMove}</span>}
                      </span>
                    )}
                  </span>
                  <span className="co-trend">
                    {e.spark && e.spark.length > 1 && <Sparkline values={e.spark} width={140} height={34} />}
                    {e.return_1y != null && <span className="co-span">{t.view.tile.priceYear(e.return_1y >= 0, `${Math.abs(e.return_1y).toFixed(1)}%`)}</span>}
                  </span>
                  <span className="co-score">
                    <Mix c={e.counts} total={e.promises} />
                    <span className="co-score-text">
                      {t.verdict.Kept} <b>{e.counts.Kept}</b>, {t.verdict.Missed} <b>{e.counts.Missed}</b>
                      {decided ? ` (${t.companies.trackOf(e.counts.Kept, decided)})` : ""}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
        <p className="small-print"><Link href="/companies">{h.allCompanies}</Link></p>
      </section>

      <section className="how" aria-label={t.nav.method}>
        {h.how.map((x, i) => (
          <div key={x.h}>
            <h3>{x.h}</h3>
            <p>{x.p}{i === 2 && <> <Link href="/method">{t.nav.method}</Link></>}</p>
          </div>
        ))}
      </section>
    </>
  );
}
