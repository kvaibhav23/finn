// The analysis worker is a GitHub Actions workflow (.github/workflows/ledger.yml): a fresh ledger
// takes ~10 minutes, longer than a Vercel function may run.
import type { Run } from "./guards";

const WORKFLOW = "ledger.yml";

export const configured = () => Boolean(process.env.GITHUB_TOKEN && process.env.GITHUB_REPO);

async function gh(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`https://api.github.com/repos/${process.env.GITHUB_REPO}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init.headers ?? {}),
    },
  });
}

interface ApiRun { id: number; display_title: string; status: string; conclusion: string | null; created_at: string }

export async function recentRuns(): Promise<Run[]> {
  const r = await gh(`/actions/workflows/${WORKFLOW}/runs?per_page=50`);
  if (!r.ok) throw new Error(`GitHub runs: HTTP ${r.status}`);
  const body = (await r.json()) as { workflow_runs: ApiRun[] };
  return body.workflow_runs.map((w) => ({
    id: w.id, name: w.display_title, status: w.status, conclusion: w.conclusion, created_at: w.created_at,
  }));
}

export async function dispatch(symbol: string): Promise<void> {
  const r = await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: "main", inputs: { symbol } }),
  });
  if (r.status !== 204) throw new Error(`GitHub dispatch: HTTP ${r.status}`);
}

/** Name of the step a running analysis is on, e.g. "Read earnings calls and check promises". */
export async function currentStep(runId: number): Promise<string | null> {
  const r = await gh(`/actions/runs/${runId}/jobs`);
  if (!r.ok) return null;
  const body = (await r.json()) as { jobs: { steps?: { name: string; status: string }[] }[] };
  return body.jobs[0]?.steps?.find((s) => s.status === "in_progress")?.name ?? null;
}
