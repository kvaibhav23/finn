import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AlertsSignup } from "@/components/AlertsSignup";
import { Filings } from "@/components/Filings";
import { KeyNumbers } from "@/components/KeyNumbers";
import { LedgerView } from "@/components/LedgerView";
import { PriceChart } from "@/components/PriceChart";
import { QuarterBars } from "@/components/QuarterBars";
import { RequestAnalysis } from "@/components/RequestAnalysis";
import { Search } from "@/components/Search";
import { Signals } from "@/components/Signals";
import { channels } from "@/lib/alerts/config";
import { companyName, getIndex, getLedger, getMarket } from "@/lib/data";
import { dayMonthYear, displayName, monthYear, quarter, rupees, signedPct } from "@/lib/format";
import { getT } from "@/lib/i18n/server";
import { moveDetail, moveTitle, summary } from "@/lib/sentences";
import { VERDICTS } from "@/lib/types";

export const dynamic = "force-dynamic";   // the reader's language comes from a cookie

const FILING_DAYS = 90;

type Props = { params: Promise<{ symbol: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const symbol = decodeURIComponent((await params).symbol).toUpperCase();
  const { t } = await getT();
  const name = (await getLedger(symbol))?.name ?? (await companyName(symbol));
  return { title: name ? `${displayName(name, symbol)}: ${t.company.titleSuffix}` : symbol };
}

export default async function CompanyPage({ params }: Props) {
  const symbol = decodeURIComponent((await params).symbol).toUpperCase();
  const [{ t, lang }, ledger, market, listed, index] = await Promise.all([
    getT(), getLedger(symbol), getMarket(symbol), companyName(symbol), getIndex()]);
  if (!ledger && !listed) notFound();
  const name = displayName(ledger?.name ?? listed, symbol);
  const analysed = index.map((i) => i.symbol);
  const ok = ledger?.status === "ok";
  const p = market?.price ?? null;
  const rows = market?.prices?.rows ?? [];
  const filings = market?.filings ?? null;
  const counts = ok
    ? Object.fromEntries(VERDICTS.map((v) => [v, ledger!.promises.filter((x) => x.verdict === v).length]))
    : null;
  const lines = market ? summary(t, lang, symbol, market, counts) : [];
  const move = market?.move ?? null;

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
                {p.change > 0 ? "+" : p.change < 0 ? "−" : ""}{Math.abs(p.change).toFixed(2)} ({signedPct(p.change_pct, 2)}) {t.company.onTheDay}
              </span>
            )}
            <span className="asof">{t.company.asOf(dayMonthYear(p.as_of, lang))}</span>
          </p>
        )}
        {move && move.date === p?.as_of && (
          <div className={`move-note ${move.change_pct < 0 ? "down" : "up"}`} role="note">
            <p className="move-title">{moveTitle(t, lang, move)}.</p>
            {moveDetail(t, move) && <p>{moveDetail(t, move)}</p>}
            {move.filings.length > 0 ? (
              <p>
                {t.move.filings}{" "}
                {move.filings.map((f, i) => (
                  <span key={f.pdf_url}>
                    {i > 0 && ", "}
                    <a href={f.pdf_url} target="_blank" rel="noreferrer">{t.filings.tag[f.tag] ?? f.tag}</a>
                  </span>
                ))}
              </p>
            ) : <p>{t.move.noFilings}</p>}
          </div>
        )}
        {lines.length > 0 && (
          <div className="summary">
            {lines.map((line) => <p key={line}>{line}</p>)}
          </div>
        )}
        {market && <AlertsSignup symbol={symbol} name={name} channels={channels()} />}
        {lang !== "en" && <p className="small-print">{t.company.englishNote}</p>}
      </div>

      {(market || ok) && (
        <nav className="section-nav" aria-label={t.company.onThisPage}>
          {market && <a href="#overview">{t.company.overview}</a>}
          {ok && <a href="#promises">{t.company.promises} <span className="n">{ledger!.promises.length}</span></a>}
          {filings && <a href="#filings">{t.company.filings} <span className="n">{filings.length}</span></a>}
        </nav>
      )}

      {market && (
        <section id="overview" className="section" aria-label={t.company.overview}>
          {rows.length > 1 && (
            <PriceChart rows={rows} nifty={market.nifty} calls={market.calls ?? []}
                        ledgerQuarters={ok ? ledger!.calls.map((c) => c.quarter) : []}
                        adjustedFor={market.prices?.adjusted_for ?? []} />
          )}
          <KeyNumbers price={p} results={market.results} />
          {market.results && market.results.quarters.length > 1 && (
            <QuarterBars quarters={market.results.quarters} topLine={market.results.top_line} t={t} />
          )}
          {market.signals.length > 0 && (
            <>
              <h2 className="sub-title">{t.company.signalsTitle}</h2>
              <p className="section-sub">{t.company.signalsSub}</p>
              <Signals signals={market.signals} t={t} lang={lang} />
            </>
          )}
        </section>
      )}

      <section id="promises" className="section" aria-labelledby="promises-title">
        <h2 className="section-title" id="promises-title">{t.company.promises}</h2>
        {ok && (
          <p className="section-sub">
            {t.company.promisesSub(ledger!.calls.length, quarter(ledger!.calls[0]?.quarter),
              quarter(ledger!.calls.at(-1)?.quarter), monthYear(ledger!.as_of_results, lang))}
            {ledger!.margin_note && t.company.marginNote(ledger!.margin_note.split(":")[0])}
          </p>
        )}
        {ok && <LedgerView ledger={ledger!} />}
        {ledger?.status === "no_transcripts" && <p className="notice">{t.request.noTranscripts(name)}</p>}
        {(!ledger || ledger.status === "failed") && listed && (
          <RequestAnalysis symbol={symbol} name={name} retry={ledger?.status === "failed"} />
        )}
        {ok && (
          <p className="small-print">{t.company.readCount(ledger!.candidates ?? 0, ledger!.promises.length, ledger!.rejected ?? 0)}</p>
        )}
      </section>

      {filings && (
        <section id="filings" className="section" aria-labelledby="filings-title">
          <h2 className="section-title" id="filings-title">{t.company.filings}</h2>
          <p className="section-sub">{t.company.filingsSub(name, FILING_DAYS)}</p>
          <Filings filings={filings} days={FILING_DAYS} />
        </section>
      )}
    </>
  );
}
