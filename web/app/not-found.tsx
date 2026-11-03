import Link from "next/link";

import { getT } from "@/lib/i18n/server";

export default async function NotFound() {
  const { t } = await getT();
  return (
    <section className="prose">
      <h1>{t.notFound.title}</h1>
      <p className="lede">{t.notFound.lede}</p>
      <p><Link href="/companies">{t.notFound.link}</Link></p>
    </section>
  );
}
