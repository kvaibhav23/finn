import type { Metadata } from "next";

import { CompaniesTable } from "@/components/CompaniesTable";
import { MarketBanner } from "@/components/MarketBanner";
import { Search } from "@/components/Search";
import { getIndex, getMarketDay } from "@/lib/data";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getT()).t.companies.title };
}

export default async function Companies() {
  const [{ t, lang }, index, day] = await Promise.all([getT(), getIndex(), getMarketDay()]);
  const ready = index.filter((i) => i.status === "ok");
  return (
    <>
      <section className="page-head">
        <h1>{t.companies.title}</h1>
        <p className="lede">{t.companies.lede}</p>
        <div className="page-search"><Search analysed={index.map((i) => i.symbol)} /></div>
      </section>
      {day && <MarketBanner day={day} t={t} lang={lang} always />}
      {ready.length ? <CompaniesTable rows={ready} /> : <p className="empty">{t.companies.none}</p>}
      <p className="small-print">{t.companies.request}</p>
    </>
  );
}
