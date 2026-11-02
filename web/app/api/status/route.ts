import { NextResponse } from "next/server";

import { getIndex } from "@/lib/data";
import { configured, currentStep, recentRuns } from "@/lib/github";
import { progress, runName } from "@/lib/guards";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const symbol = (new URL(req.url).searchParams.get("symbol") ?? "").trim().toUpperCase();
  const entry = (await getIndex()).find((e) => e.symbol === symbol) ?? null;
  if (!configured()) {
    return NextResponse.json(entry ? { state: "published", status: entry.status } : { state: "none" });
  }
  try {
    const runs = await recentRuns();
    const live = runs.find((r) => r.name === runName(symbol) && r.status === "in_progress");
    return NextResponse.json(progress(symbol, runs, entry, live ? await currentStep(live.id) : null));
  } catch (e) {
    console.error(e);
    return NextResponse.json({ state: "unknown" }, { status: 502 });
  }
}
