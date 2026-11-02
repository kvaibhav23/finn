import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Filings } from "@/components/Filings";
import { KeyNumbers } from "@/components/KeyNumbers";
import { LedgerView } from "@/components/LedgerView";
import { PriceChart } from "@/components/PriceChart";
import { QuarterBars } from "@/components/QuarterBars";
import { RequestAnalysis } from "@/components/RequestAnalysis";
import { Search } from "@/components/Search";
import { Signals } from "@/components/Signals";
import { companyName, getIndex, getLedger, getMarket } from "@/lib/data";
import { dayMonthYear, displayName, monthYear, quarter, rupees, signedPct } from "@/lib/format";

export const dynamicParams = true;

const FILING_DAYS = 90;

export async function generateStaticParams() {
  return (await getIndex()).map((e) => ({ symbol: e.symbol }));
}

type Props = { params: Promise<{ symbol: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const symbol = decodeURIComponent((await params).symbol).toUpperCase();
  const name = (await getLedger(symbol))?.name ?? (await companyName(symbol));
  return { title: name ? `${displayName(name, symbol)}: price, results and promise ledger` : symbol };
}

export default async function CompanyPage({ params }: Props) {
  const symbol = decodeURIComponent((await params).symbol).toUpperCase();
  const [ledger, market, listed, index] = await Promise.all([
    getLedger(symbol), getMarket(symbol), companyName(symbol), getIndex()]);
  if (!ledger && !listed) notFound();
  const name = displayName(ledger?.name ?? listed, symbol);
  const analysed = index.map((i) => i.symbol);
  const ok = ledger?.status === "ok";
  const p = market?.price ?? null;
  const rows = market?.prices?.rows ?? [];
  const filings = market?.filings ?? null;

  return (
    <>
      <div className="co-head">
        <div className="co-top">
          <h1>{name}<span className="co-sym">{symbol}</span></h1>
          <div className="head-search"><Search analysed={analysed} compact /></div>
        </div>
        {p && (
          <p className="quote-line">
            <span className="last">{rupees(p.close)}</span>
            {p.change != null && p.change_pct != null && (
              <span className={`chg ${p.change > 0 ? "up" : p.change < 0 ? "down" : ""}`}>
                {p.change > 0 ? "+" : p.change < 0 ? "−" : ""}{Math.abs(p.change).toFixed(2)} ({signedPct(p.change_pct, 2)}) on the day
              </span>
            )}
            <span className="asof">NSE close on {dayMonthYear(p.as_of)}. Updated every weekday night.</span>
          </p>
        )}
        {market?.summary?.length ? (
          <div className="summary">
            {market.summary.map((line) => <p key={line}>{line}</p>)}
          </div>
        ) : null}
      </div>

      {(market || ok) && (
        <nav className="section-nav" aria-label="On this page">
          {market && <a href="#overview">Overview</a>}
          {ok && <a href="#promises">Promises <span className="n">{ledger!.promises.length}</span></a>}
          {filings && <a href="#filings">Filings <span className="n">{filings.length}</span></a>}
        </nav>
      )}

      {market && (
        <section id="overview" className="section" aria-label="Overview">
          {rows.length > 1 && (
            <PriceChart rows={rows} nifty={market.nifty} calls={market.calls ?? []}
                        ledgerQuarters={ok ? ledger!.calls.map((c) => c.quarter) : []}
                        adjustedFor={market.prices?.adjusted_for ?? []} />
          )}
          <KeyNumbers price={p} results={market.results} />
          {market.results && market.results.quarters.length > 1 && (
            <QuarterBars quarters={market.results.quarters} topLine={market.results.top_line} />
          )}
          {market.signals.length > 0 && (
            <>
              <h2 className="sub-title">Signals</h2>
              <p className="section-sub">Facts worth knowing, each with its source. Not a rating, and not advice.</p>
              <Signals signals={market.signals} />
            </>
          )}
        </section>
      )}

      <section id="promises" className="section" aria-labelledby="promises-title">
        <h2 className="section-title" id="promises-title">Promises</h2>
        {ok && (
          <p className="section-sub">
            What management said on {ledger!.calls.length} earnings calls, {quarter(ledger!.calls[0]?.quarter)} to{" "}
            {quarter(ledger!.calls.at(-1)?.quarter)}, checked against results filed up to {monthYear(ledger!.as_of_results)}.
            {ledger!.margin_note && <> Margins use the definition management itself reports: {ledger!.margin_note.split(":")[0]}.</>}
          </p>
        )}
        {ok && <LedgerView ledger={ledger!} />}
        {ledger?.status === "no_transcripts" && <p className="notice">{ledger.message}</p>}
        {(!ledger || ledger.status === "failed") && listed && (
          <RequestAnalysis symbol={symbol} name={name} retry={ledger?.status === "failed"} />
        )}
        {ok && (
          <p className="small-print">
            FINN read {ledger!.candidates} forward-looking sentences by management and kept {ledger!.promises.length}{" "}
            checkable promises. Quotes that could not be found word for word in a transcript were discarded
            ({ledger!.rejected}).
          </p>
        )}
      </section>

      {filings && (
        <section id="filings" className="section" aria-labelledby="filings-title">
          <h2 className="section-title" id="filings-title">Filings</h2>
          <p className="section-sub">
            What {name} told NSE in the last {FILING_DAYS} days, newest first. Each links the company&apos;s own
            document. Routine paperwork is left out.
          </p>
          <Filings filings={filings} days={FILING_DAYS} />
        </section>
      )}
    </>
  );
}
