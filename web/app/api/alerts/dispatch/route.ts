import { timingSafeEqual } from "node:crypto";

import { NextResponse } from "next/server";

import { alertsSecret, channels, siteUrl, whatsappConfig } from "@/lib/alerts/config";
import { wants, type EventKind } from "@/lib/alerts/core";
import { emailHtml, emailText, message, type AlertEvent } from "@/lib/alerts/messages";
import { sendEmail, sendWhatsApp } from "@/lib/alerts/send";
import { followers, markSent } from "@/lib/alerts/store";
import { companyName } from "@/lib/data";
import { displayName } from "@/lib/format";
import { dict } from "@/lib/i18n";

export const runtime = "nodejs";
export const maxDuration = 300;

function authorised(req: Request): boolean {
  const secret = alertsSecret();
  const got = (req.headers.get("authorization") ?? "").replace(/^Bearer /, "");
  return Boolean(secret) && got.length === secret.length && timingSafeEqual(Buffer.from(got), Buffer.from(secret));
}

// Called by the GitHub workflows after new data is published (scripts/send_alerts.py).
export async function POST(req: Request) {
  if (!authorised(req)) return NextResponse.json({ error: "unauthorised" }, { status: 401 });
  const on = channels();
  if (!on.email && !on.whatsapp) return NextResponse.json({ sent: 0, note: "alerts not configured" });
  const { events = [] } = (await req.json().catch(() => ({}))) as { events?: AlertEvent[] };
  const site = siteUrl();
  const w = whatsappConfig();
  let sent = 0, skipped = 0, failed = 0;

  for (const e of events.slice(0, 200)) {
    if (!/^[A-Z0-9&_-]{1,20}$/.test(e.symbol)) continue;
    const name = displayName(await companyName(e.symbol), e.symbol);
    for (const { token, sub } of await followers(e.symbol)) {
      if (!wants(sub, e.symbol, e.kind as EventKind) || !on[sub.channel]) { skipped++; continue; }
      if (!(await markSent(e.id, token))) { skipped++; continue; }
      try {
        if (sub.channel === "email") {
          const t = dict(sub.lang);
          const m = message(t, sub.lang, e, name, site);
          const stopOne = `${site}/api/alerts/unsubscribe?t=${token}&s=${encodeURIComponent(e.symbol)}`;
          const stopAll = `${site}/api/alerts/unsubscribe?t=${token}`;
          await sendEmail(sub.address, m.subject, emailHtml(t, m, e.symbol, stopOne, stopAll),
            emailText(t, m, e.symbol, stopOne, stopAll), stopAll);
        } else {
          // WhatsApp templates are approved in one language (English): company, what happened, link.
          const m = message(dict("en"), "en", e, name, site);
          await sendWhatsApp(sub.address, w.alertTemplate, [name, m.text, m.link]);
        }
        sent++;
      } catch {
        failed++;
      }
    }
  }
  return NextResponse.json({ sent, skipped, failed });
}
