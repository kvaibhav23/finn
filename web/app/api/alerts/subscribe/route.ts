import { NextResponse } from "next/server";

import { channels, siteUrl, whatsappConfig } from "@/lib/alerts/config";
import { merge, parseSignup } from "@/lib/alerts/core";
import { confirmHtml } from "@/lib/alerts/messages";
import { sendEmail, sendWhatsApp } from "@/lib/alerts/send";
import { getSub, newToken, saveSub, tokenFor, underLimit } from "@/lib/alerts/store";
import { companyName } from "@/lib/data";
import { displayName } from "@/lib/format";
import { dict } from "@/lib/i18n";

export const runtime = "nodejs";

const fail = (error: string, status = 400) => NextResponse.json({ state: "error", error }, { status });

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  if (body.website) return NextResponse.json({ state: "ok" });          // a bot filled the hidden field
  const parsed = parseSignup(body);
  if (!parsed.ok) return fail(parsed.error);
  const s = parsed.value;
  if (!channels()[s.channel]) return fail("off", 503);
  const listed = await companyName(s.symbol);
  if (!listed) return fail("symbol");

  try {
    const ip = (req.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "unknown";
    if (!(await underLimit(ip))) return fail("rate", 429);
    const existingToken = await tokenFor(s.channel, s.address);
    const existing = existingToken ? await getSub(existingToken) : null;
    const token = existing ? existingToken! : newToken();
    const sub = merge(existing, s, new Date().toISOString());
    await saveSub(token, sub);

    const t = dict(sub.lang);
    const name = displayName(listed, s.symbol);
    if (sub.channel === "email") {
      if (sub.confirmed) return NextResponse.json({ state: "added" });
      const url = `${siteUrl()}/api/alerts/confirm?t=${token}`;
      await sendEmail(sub.address, t.msg.confirmSubject, confirmHtml(t, s.symbol, url),
        `${t.msg.confirmBody(s.symbol)}\n\n${url}`);
      return NextResponse.json({ state: "check_email" });
    }
    const w = whatsappConfig();
    await sendWhatsApp(sub.address, w.welcomeTemplate, [name]);
    return NextResponse.json({ state: "whatsapp_on" });
  } catch {
    return fail("error", 502);
  }
}
