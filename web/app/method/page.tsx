import type { Metadata } from "next";

import { VerdictMark } from "@/components/VerdictMark";
import { METHOD } from "@/lib/i18n/method";
import { getT } from "@/lib/i18n/server";
import { VERDICTS } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getT()).t.nav.method };
}

export default async function Method() {
  const { t, lang } = await getT();
  const m = METHOD[lang];
  return (
    <article className="prose">
      <h1>{m.title}</h1>
      <p className="lede">{m.lede}</p>
      {m.steps.map((s) => (
        <section key={s.h}>
          <h2>{s.h}</h2>
          <p>{s.p}</p>
        </section>
      ))}
      <dl>
        {VERDICTS.map((v) => (
          <div key={v} style={{ display: "contents" }}>
            <dt><VerdictMark verdict={v} /> {t.verdict[v]}</dt>
            <dd>{t.meaning[v]}</dd>
          </div>
        ))}
      </dl>

      <h2>{m.pricesTitle}</h2>
      <p>{m.pricesIntro}</p>
      <ul>
        {m.bullets.map((b) => <li key={b.b}><b>{b.b}</b> {b.p}</li>)}
      </ul>
      <p>{m.rerun}</p>

      <h2>{m.keepTitle}</h2>
      <p>{m.keep}</p>
    </article>
  );
}
