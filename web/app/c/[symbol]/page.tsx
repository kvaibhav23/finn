import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { LedgerView } from "@/components/LedgerView";
import { RequestAnalysis } from "@/components/RequestAnalysis";
import { Search } from "@/components/Search";
import { companyName, getIndex, getLedger } from "@/lib/data";
import { displayName, monthYear, quarter } from "@/lib/format";

export const dynamicParams = true;

export async function generateStaticParams() {
  return (await getIndex()).map((e) => ({ symbol: e.symbol }));
}

type Props = { params: Promise<{ symbol: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const symbol = decodeURIComponent((await params).symbol).toUpperCase();
  const name = (await getLedger(symbol))?.name ?? (await companyName(symbol));
  return { title: name ? `${displayName(name, symbol)} promise ledger` : symbol };
}

export default async function CompanyPage({ params }: Props) {
  const symbol = decodeURIComponent((await params).symbol).toUpperCase();
  const [ledger, listed, index] = await Promise.all([getLedger(symbol), companyName(symbol), getIndex()]);
  if (!ledger && !listed) notFound();
  const name = displayName(ledger?.name ?? listed, symbol);
  const analysed = index.map((i) => i.symbol);

  return (
    <>
      <div className="co-head">
        <div style={{ display: "flex", gap: 24, alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap" }}>
          <h1>{name}<span className="co-sym">{symbol}</span></h1>
          <div className="head-search"><Search analysed={analysed} compact /></div>
        </div>
        {ledger?.status === "ok" && (
          <p className="co-meta">
            {ledger.calls.length} earnings calls, {quarter(ledger.calls[0]?.quarter)} to{" "}
            {quarter(ledger.calls.at(-1)?.quarter)}. Results checked up to {monthYear(ledger.as_of_results)}.
            {ledger.margin_note && <> Margins use the definition management itself reports: {ledger.margin_note.split(":")[0]}.</>}
          </p>
        )}
      </div>

      {ledger?.status === "ok" && <LedgerView ledger={ledger} />}

      {ledger?.status === "no_transcripts" && (
        <p className="notice">{ledger.message}</p>
      )}

      {(!ledger || ledger.status === "failed") && listed && (
        <RequestAnalysis symbol={symbol} name={name} retry={ledger?.status === "failed"} />
      )}

      {ledger?.status === "ok" && (
        <p className="co-meta" style={{ marginTop: 28, fontSize: "var(--s13)" }}>
          FINN read {ledger.candidates} forward-looking sentences by management and kept {ledger.promises.length} checkable
          promises. Quotes that could not be found word for word in a transcript were discarded ({ledger.rejected}).
        </p>
      )}
    </>
  );
}
