import { NextResponse } from "next/server";

import { siteUrl } from "@/lib/alerts/config";
import { deleteSub, dropSymbol, getSub } from "@/lib/alerts/store";

export const runtime = "nodejs";

// ?t=<token> stops everything and deletes the details; &s=SYMBOL stops one company.
// POST does it: the button on the Settings page, and the one-click unsubscribe mail apps send (RFC 8058).
// GET (the link in an email) only opens that page: link scanners in mail systems open links by themselves.
async function stop(req: Request): Promise<"stopped" | "stopped_one" | "invalid"> {
  const q = new URL(req.url).searchParams;
  const token = q.get("t") ?? "";
  const symbol = (q.get("s") ?? "").toUpperCase();
  const sub = await getSub(token).catch(() => null);
  if (!sub) return "invalid";
  if (symbol && sub.symbols.includes(symbol) && sub.symbols.length > 1) {
    await dropSymbol(token, sub, symbol);
    return "stopped_one";
  }
  await deleteSub(token, sub);
  return "stopped";
}

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  const t = encodeURIComponent(q.get("t") ?? "");
  const s = q.get("s") ? `&s=${encodeURIComponent(q.get("s")!.toUpperCase())}` : "";
  return NextResponse.redirect(`${siteUrl()}/settings?stop=${t}${s}`, 303);
}

export async function POST(req: Request) {
  const result = await stop(req);
  return NextResponse.json({ state: result }, { status: result === "invalid" ? 404 : 200 });
}
