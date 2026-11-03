import type { Metadata } from "next";

import { Digest } from "@/components/Digest";
import { getDigest, getPortfolio } from "@/lib/data";
import { getT } from "@/lib/i18n/server";
import { WINDOWS } from "@/lib/watch";

export const dynamic = "force-dynamic";   // the reader's language comes from a cookie; the window ends now

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getT()).t.digest.title };
}

export default async function DigestPage({ searchParams }: { searchParams: Promise<{ w?: string }> }) {
  const [{ t }, digest, portfolio, { w }] = await Promise.all([getT(), getDigest(), getPortfolio(), searchParams]);
  return (
    <>
      <section className="page-head">
        <h1>{t.digest.title}</h1>
        <p className="lede">{t.digest.lede(portfolio.length)}</p>
      </section>
      {digest ? <Digest digest={digest} now={Date.now()} initial={WINDOWS.find((x) => x === w) ?? "1"} /> : <p className="empty">{t.digest.empty("—")}</p>}
    </>
  );
}
