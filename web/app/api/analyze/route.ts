import { NextResponse } from "next/server";

import { getIndex, getSymbols } from "@/lib/data";
import { configured, dispatch, recentRuns } from "@/lib/github";
import { decide } from "@/lib/guards";

export const dynamic = "force-dynamic";

const MESSAGES = {
  unknown_symbol: "That symbol isn't listed on the NSE main board.",
  busy: "Another company is being analysed right now. Try again in about 10 minutes.",
  limit: "Today's analysis limit has been reached. Try again tomorrow.",
  unavailable: "Analysis requests are switched off on this site.",
  error: "The analysis could not be started. Try again in a minute.",
};

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as { symbol?: string };
  const symbol = String(body.symbol ?? "").trim().toUpperCase();
  const known = (await getSymbols()).some(([s]) => s === symbol);
  const entry = (await getIndex()).find((e) => e.symbol === symbol) ?? null;
  if (!configured()) {
    return NextResponse.json({ state: "unavailable", message: MESSAGES.unavailable }, { status: 503 });
  }
  try {
    const d = decide({ symbol, known, entry, runs: await recentRuns(), now: Date.now() });
    switch (d.action) {
      case "unknown_symbol":
        return NextResponse.json({ state: "unknown_symbol", message: MESSAGES.unknown_symbol }, { status: 404 });
      case "ready":
        return NextResponse.json({ state: "ready" });
      case "running":
        return NextResponse.json({ state: d.run.status === "in_progress" ? "running" : "queued" });
      case "busy":
        return NextResponse.json({ state: "busy", message: MESSAGES.busy }, { status: 409 });
      case "limit":
        return NextResponse.json({ state: "limit", message: MESSAGES.limit }, { status: 429 });
      case "dispatch":
        await dispatch(symbol);
        return NextResponse.json({ state: "queued" }, { status: 202 });
    }
  } catch (e) {
    console.error(e);
    return NextResponse.json({ state: "error", message: MESSAGES.error }, { status: 502 });
  }
}
