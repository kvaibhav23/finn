import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AlertsSignup } from "@/components/AlertsSignup";
import { BigDays } from "@/components/BigDays";
import { ComingUp } from "@/components/ComingUp";
import { Filings } from "@/components/Filings";
import { Glance } from "@/components/Glance";
import { KeyNumbers } from "@/components/KeyNumbers";
import { LedgerView } from "@/components/LedgerView";
import { PriceChart } from "@/components/PriceChart";
import { DeliveryBars, RangeBar, Returns } from "@/components/PriceFacts";
import { QuarterBars } from "@/components/QuarterBars";
import { RequestAnalysis } from "@/components/RequestAnalysis";
import { Search } from "@/components/Search";
import { SectionTabs, type Tab } from "@/components/SectionTabs";
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

  const today = p?.as_of ?? new Date().toISOString().slice(0, 10);

  const promises = (
    <>
      <h2 className="section-title">{t.company.promises}</h2>
      {ok && (
        <p className="section-sub">
          {t.company.promisesSub(ledger!.calls.length, quarter(ledger!.calls[0]?.quarter),
            quarter(ledger!.calls.at(-1)?.quarter), monthYear(ledger!.as_of_results, lang))}
          {ledger!.margin_note && t.company.marginNote(ledger!.margin_note.split(":")[0])}
        </p>
      )}
      {ok && <ComingUp ledger={ledger!} today={today} t={t} lang={lang} />}
      {ok && <LedgerView ledger={ledger!} />}
      {ledger?.status === "no_transcripts" && <p className="notice">{t.request.noTranscripts(name)}</p>}
      {(!ledger || ledger.status === "failed") && listed && (
        <RequestAnalysis symbol={symbol} name={name} retry={ledger?.status === "failed"} />
      )}
      {ok && (
        <p className="small-print">{t.company.readCount(ledger!.candidates ?? 0, ledger!.promises.length, ledger!.rejected ?? 0)}</p>
      )}
    </>
  );

  const tabs: Tab[] = [];
  const panels: React.ReactNode[] = [];
  const add = (id: keyof typeof t.view.tabs, node: React.ReactNode, count?: number) => {
    tabs.push({ id, label: t.view.tabs[id], count });
    panels.push(node);
  };
  if (market) {
    add("overview", (
      <>
        {lines.length > 0 && <div className="summary">{lines.map((line) => <p key={line}>{line}</p>)}</div>}
        <Glance market={market} ledger={ledger} days={FILING_DAYS} t={t} lang={lang} />
        {market.signals.length > 0 && (
          <>
            <h2 className="sub-title">{t.company.signalsTitle}</h2>
            <p className="section-sub">{t.company.signalsSub}</p>
            <Signals signals={market.signals} t={t} lang={lang} />
          </>
        )}
      </>
    ));
  }
  if (rows.length > 1) {
    add("price", (
      <>
        <PriceChart rows={rows} nifty={market!.nifty} calls={market!.calls ?? []}
                    ledgerQuarters={ok ? ledger!.calls.map((c) => c.quarter) : []}
                    adjustedFor={market!.prices?.adjusted_for ?? []} />
        <div className="pair">
          <div className="stack">
            {p && <RangeBar p={p} t={t} />}
            <BigDays rows={rows} nifty={market!.nifty} />
          </div>
          <div className="stack">
            <Returns rows={rows} nifty={market!.nifty} symbol={symbol} t={t} lang={lang} />
            <DeliveryBars rows={rows} t={t} lang={lang} />
          </div>
        </div>
      </>
    ));
  }
  if (market?.results) {
    add("results", (
      <>
        <h2 className="section-title">{t.view.keyNumbers}</h2>
        <KeyNumbers price={p} results={market.results} />
        {market.results.quarters.length > 1 && (
          <>
            <h2 className="sub-title">{t.view.quarters.title}</h2>
            <QuarterBars quarters={market.results.quarters} topLine={market.results.top_line} />
          </>
        )}
      </>
    ));
  }
  add("promises", promises, ok ? ledger!.promises.length : undefined);
  if (filings) {
    add("filings", (
      <>
        <h2 className="section-title">{t.company.filings}</h2>
        <p className="section-sub">{t.company.filingsSub(name, FILING_DAYS)}</p>
        <Filings filings={filings} days={FILING_DAYS} rows={rows} nifty={market!.nifty} end={p?.as_of ?? null} />
      </>
    ), filings.length);
  }

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
        {market && <AlertsSignup symbol={symbol} name={name} channels={channels()} />}
      </div>

      {tabs.length > 1 ? <SectionTabs tabs={tabs} panels={panels} /> : <section className="panel">{panels[0]}</section>}
      {lang !== "en" && <p className="small-print">{t.company.englishNote}</p>}
    </>
  );
}
