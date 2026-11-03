import { createHmac, timingSafeEqual } from "node:crypto";

import { NextResponse } from "next/server";

import { whatsappConfig } from "@/lib/alerts/config";
import { normalPhone } from "@/lib/alerts/core";
import { deleteSub, getSub, tokenFor } from "@/lib/alerts/store";

export const runtime = "nodejs";

const STOP = /^\s*(stop|unsubscribe|band|बंद|cancel)\s*$/i;

// Meta checks the webhook once with a GET (hub.challenge) when you add it in the app settings.
export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  const { verify } = whatsappConfig();
  if (verify && q.get("hub.mode") === "subscribe" && q.get("hub.verify_token") === verify) {
    return new Response(q.get("hub.challenge") ?? "", { status: 200 });
  }
  return new Response("forbidden", { status: 403 });
}

// Incoming messages. A reply of STOP deletes the subscriber. Requests must carry Meta's signature.
export async function POST(req: Request) {
  const raw = await req.text();
  const { appSecret } = whatsappConfig();
  const sig = (req.headers.get("x-hub-signature-256") ?? "").replace(/^sha256=/, "");
  const want = appSecret ? createHmac("sha256", appSecret).update(raw).digest("hex") : "";
  if (!want || sig.length !== want.length || !timingSafeEqual(Buffer.from(sig), Buffer.from(want))) {
    return new Response("forbidden", { status: 403 });
  }
  const body = JSON.parse(raw) as {
    entry?: { changes?: { value?: { messages?: { from: string; type: string; text?: { body: string } }[] } }[] }[];
  };
  for (const entry of body.entry ?? []) {
    for (const change of entry.changes ?? []) {
      for (const m of change.value?.messages ?? []) {
        if (m.type !== "text" || !STOP.test(m.text?.body ?? "")) continue;
        const phone = normalPhone(m.from);
        const token = phone ? await tokenFor("whatsapp", phone) : null;
        const sub = token ? await getSub(token) : null;
        if (token && sub) await deleteSub(token, sub);
      }
    }
  }
  return NextResponse.json({ ok: true });
}
