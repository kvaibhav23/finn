import type { Metadata } from "next";

import { LanguagePicker } from "@/components/LanguagePicker";
import { StopAlerts } from "@/components/StopAlerts";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getT()).t.settings.title };
}

type Props = { searchParams: Promise<Record<string, string | undefined>> };

export default async function Settings({ searchParams }: Props) {
  const { t } = await getT();
  const q = await searchParams;
  const s = t.settings;
  const status = q.alerts === "confirmed" ? s.confirmed : q.alerts === "stopped" ? s.stopped
    : q.alerts === "stopped_one" && q.s ? s.stoppedOne(q.s) : q.alerts === "invalid" ? s.invalid : null;

  return (
    <article className="prose settings">
      <h1>{s.title}</h1>
      {status && <p className={`notice${q.alerts === "invalid" ? " warn" : ""}`} role="status">{status}</p>}
      {q.stop && <StopAlerts token={q.stop} symbol={q.s?.toUpperCase() ?? null} />}

      <h2 id="language">{s.language}</h2>
      <p className="small-print">{s.languageNote}</p>
      <LanguagePicker />

      <h2 id="alerts">{s.alerts}</h2>
      <p>{s.alertsText}</p>
      <p className="small-print">{t.alerts.privacy}</p>
    </article>
  );
}
