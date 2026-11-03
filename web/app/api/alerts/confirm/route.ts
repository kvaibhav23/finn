import { NextResponse } from "next/server";

import { siteUrl } from "@/lib/alerts/config";
import { getSub, saveSub } from "@/lib/alerts/store";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("t") ?? "";
  const sub = await getSub(token).catch(() => null);
  if (!sub) return NextResponse.redirect(`${siteUrl()}/settings?alerts=invalid`, 303);
  if (!sub.confirmed) await saveSub(token, { ...sub, confirmed: true });
  return NextResponse.redirect(`${siteUrl()}/settings?alerts=confirmed`, 303);
}
