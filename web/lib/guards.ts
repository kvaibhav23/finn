// Pure decisions behind /api/analyze and /api/status (tested with node --test; no network here).

export interface Run {
  id: number;
  name: string;              // "ledger <SYMBOL>" (run-name in .github/workflows/ledger.yml)
  status: string;            // queued | in_progress | completed | waiting | requested | pending
  conclusion: string | null; // success | failure | cancelled | ...
  created_at: string;        // ISO, UTC
}

export interface Entry {
  status: string;            // ok | no_transcripts | failed
  generated_at: string;
}

export const FRESH_DAYS = 7;
export const DAILY_CAP = 15;
const ACTIVE = new Set(["queued", "in_progress", "waiting", "requested", "pending"]);
const DAY = 86_400_000;

export const runName = (symbol: string) => `ledger ${symbol}`;

/** Ledger timestamps: new ones are UTC ("...Z"); older ones were written in IST without a zone. */
export function parseTime(s: string): number {
  return Date.parse(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : `${s}+05:30`);
}

function istDate(ms: number): string {
  return new Date(ms + 5.5 * 3_600_000).toISOString().slice(0, 10);
}

export type Decision =
  | { action: "unknown_symbol" }
  | { action: "ready" }
  | { action: "running"; run: Run }
  | { action: "busy" }
  | { action: "limit" }
  | { action: "dispatch" };

export function decide(args: {
  symbol: string; known: boolean; entry: Entry | null; runs: Run[]; now: number;
  freshDays?: number; dailyCap?: number;
}): Decision {
  const { symbol, known, entry, runs, now, freshDays = FRESH_DAYS, dailyCap = DAILY_CAP } = args;
  if (!known) return { action: "unknown_symbol" };
  if (entry && entry.status !== "failed" && now - parseTime(entry.generated_at) < freshDays * DAY) {
    return { action: "ready" };
  }
  const active = runs.filter((r) => ACTIVE.has(r.status));
  const mine = active.find((r) => r.name === runName(symbol));
  if (mine) return { action: "running", run: mine };
  if (active.length) return { action: "busy" };              // one at a time: Gemini free tier
  const today = istDate(now);
  if (runs.filter((r) => istDate(Date.parse(r.created_at)) === today).length >= dailyCap) {
    return { action: "limit" };
  }
  return { action: "dispatch" };
}

export type Progress =
  | { state: "none" }
  | { state: "queued" }
  | { state: "running"; step: string | null }
  | { state: "publishing" }
  | { state: "published"; status: string }
  | { state: "failed" };

/** Where the latest run for `symbol` stands; `published` = this deployment already has its ledger. */
export function progress(symbol: string, runs: Run[], entry: Entry | null, step: string | null = null): Progress {
  const latest = runs
    .filter((r) => r.name === runName(symbol))
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
  const fresh = entry && latest ? parseTime(entry.generated_at) >= Date.parse(latest.created_at) : false;
  if (entry && (fresh || !latest)) return { state: "published", status: entry.status };
  if (!latest) return { state: "none" };
  if (latest.status === "completed") {
    return latest.conclusion === "success" || entry?.status === "failed" ? { state: "publishing" } : { state: "failed" };
  }
  return latest.status === "in_progress" ? { state: "running", step } : { state: "queued" };
}
