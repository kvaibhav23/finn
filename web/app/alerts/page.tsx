import type { Metadata } from "next";

import { AlertsInbox, type Watched } from "@/components/AlertsInbox";
import { getDigest, getMarket, getPortfolio } from "@/lib/data";
import { displayName } from "@/lib/format";
import { getT } from "@/lib/i18n/server";
import { ALERT_SESSIONS, VOLUME_DAYS } from "@/lib/watch";

export const dynamic = "force-dynamic";   // the reader's language comes from a cookie

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getT()).t.inbox.title };
}

export default async function AlertsPage() {
  const [{ t }, portfolio, digest] = await Promise.all([getT(), getPortfolio(), getDigest()]);
  const markets = await Promise.all(portfolio.map((p) => getMarket(p.symbol)));
  // Only what the rules need: enough sessions for a 50-day volume average before each of the last 20 days.
  const companies: Watched[] = portfolio.map((p, i) => ({
    symbol: p.symbol, name: displayName(p.name, p.symbol),
    rows: (markets[i]?.prices?.rows ?? []).slice(-(ALERT_SESSIONS + VOLUME_DAYS + 1)).map((r) => [r[0], r[1], r[2]] as [string, number, number]),
  }));
  const symbols = new Set(portfolio.map((p) => p.symbol));
  const filings = (digest?.items ?? []).filter((f) => symbols.has(f.symbol)).map(({ card, profile, ...f }) => f);
  return (
    <>
      <section className="page-head">
        <h1>{t.inbox.title}</h1>
        <p className="lede">{t.inbox.lede(portfolio.length)}</p>
      </section>
      <AlertsInbox companies={companies} filings={filings} />
    </>
  );
}
