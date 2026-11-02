import Link from "next/link";

import { Search } from "@/components/Search";
import { Track } from "@/components/Track";
import { VerdictMark } from "@/components/VerdictMark";
import { getIndex, getLedger } from "@/lib/data";
import { displayName, monthYear, quarter } from "@/lib/format";
import type { IndexEntry, Ledger, Promise_ } from "@/lib/types";

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
  const index = await getIndex();
  const ex = await example(index);
  const ready = index.filter((i) => i.status === "ok");

  return (
    <>
      <section className="home-hero">
        <h1>Did management do what they said?</h1>
        <p className="lede">
          FINN reads the earnings calls of NSE-listed companies, finds every promise that can be checked, and checks
          it against the results they filed later. Every verdict shows the exact words and where they came from.
        </p>
        <Search analysed={index.map((i) => i.symbol)} autoFocus />
      </section>

      {ex && (
        <section className="example" aria-label="An example from a real ledger">
          <div className="example-grid">
            <div>
              <p className="example-who">
                {displayName(ex.ledger.name, ex.ledger.symbol)}, {ex.p.speaker}, {quarter(ex.p.quarter)} earnings call
              </p>
              <blockquote className="quote">“{ex.p.quote}”</blockquote>
            </div>
            <div className="example-out">
              <Track p={ex.p} calls={ex.ledger.calls} asOf={ex.ledger.as_of_results} />
              <p className="example-line">
                <span className="row-verdict v-kept" style={{ justifyContent: "flex-start" }}>
                  <VerdictMark verdict="Kept" /> Kept
                </span>{" "}
                {ex.p.title}, came in at <strong>{ex.p.actual!.text}</strong> for the period ending{" "}
                {monthYear(ex.p.due)}, from the filed results.
              </p>
              <Link href={`/c/${ex.ledger.symbol}`}>See all {ex.ledger.promises.length} promises</Link>
            </div>
          </div>
        </section>
      )}

      <section aria-labelledby="ready-title">
        <h2 className="section-title" id="ready-title">Ledgers ready to read</h2>
        <p className="section-sub">Search above to request any other NSE company.</p>
        <ul className="co-list">
          {ready.map((e) => {
            const decided = e.counts.Kept + e.counts.Missed;
            return (
              <li key={e.symbol}>
                <Link href={`/c/${e.symbol}`} className="co-row">
                  <span className="co-name">
                    {displayName(e.name, e.symbol)}<span className="co-sym">{e.symbol}</span>
                  </span>
                  <span className="co-span">
                    {e.calls} calls, {quarter(e.from)} to {quarter(e.to)}
                  </span>
                  <span className="co-score">
                    <Mix c={e.counts} total={e.promises} />
                    <span className="co-score-text">
                      <b>{e.counts.Kept}</b> kept, <b>{e.counts.Missed}</b> missed of {decided} decided;{" "}
                      {e.promises} promises
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="how" aria-label="How FINN checks a promise">
        <div>
          <h3>Only what was said</h3>
          <p>Every promise is quoted word for word from the transcript, with the speaker and page. Anything FINN can&apos;t find verbatim is thrown out.</p>
        </div>
        <div>
          <h3>Numbers from filings</h3>
          <p>Actuals come from the results the company filed with NSE, or from management&apos;s own later words, labelled as such.</p>
        </div>
        <div>
          <h3>Verdicts by rule</h3>
          <p>Kept, missed, revised or dropped is decided by fixed rules anyone can read. <Link href="/method">How it works</Link></p>
        </div>
      </section>
    </>
  );
}
