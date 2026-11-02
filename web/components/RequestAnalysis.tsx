"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type State =
  | "idle" | "starting" | "queued" | "running" | "publishing" | "published"
  | "failed" | "busy" | "limit" | "unavailable" | "error" | "unknown_symbol";

const STEPS = ["Queued", "Reading the earnings calls and checking each promise", "Publishing the ledger"];
const POLL_MS = 15_000;

function stepIndex(state: State, step: string | null): number {
  if (state === "publishing" || state === "published") return 2;
  if (state === "running") return step && /build|publish/i.test(step) ? 2 : step && /read/i.test(step) ? 1 : 0;
  return 0;
}

export function RequestAnalysis({ symbol, name, retry = false }: { symbol: string; name: string; retry?: boolean }) {
  const [state, setState] = useState<State>("idle");
  const [step, setStep] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = useCallback(async () => {
    try {
      const r = await fetch(`/api/status?symbol=${encodeURIComponent(symbol)}`, { cache: "no-store" });
      const s = (await r.json()) as { state: State | "none" | "unknown"; step?: string | null };
      if (s.state === "published") { window.location.reload(); return; }
      if (s.state === "failed") { setState("failed"); return; }
      if (s.state === "queued" || s.state === "running" || s.state === "publishing") {
        setState(s.state);
        setStep(s.step ?? null);
      }
    } catch { /* network blip: keep polling */ }
    timer.current = setTimeout(poll, POLL_MS);
  }, [symbol]);

  // Someone may already have started this company: pick up a run in progress on load.
  useEffect(() => {
    fetch(`/api/status?symbol=${encodeURIComponent(symbol)}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((s: { state: string }) => {
        if (["queued", "running", "publishing"].includes(s.state)) { setState(s.state as State); poll(); }
      })
      .catch(() => {});
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [symbol, poll]);

  async function start() {
    setState("starting");
    setMessage(null);
    try {
      const r = await fetch("/api/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol }),
      });
      const s = (await r.json()) as { state: State | "ready"; message?: string };
      if (s.state === "ready") { window.location.reload(); return; }
      setState(s.state);
      setMessage(s.message ?? null);
      if (s.state === "queued" || s.state === "running") timer.current = setTimeout(poll, POLL_MS);
    } catch {
      setState("error");
      setMessage("The analysis could not be started. Check your connection and try again.");
    }
  }

  const working = state === "queued" || state === "running" || state === "publishing";
  const at = stepIndex(state, step);

  return (
    <section className="request" aria-live="polite">
      {!working && (
        <>
          <p>
            {retry
              ? `The last analysis of ${name} stopped before it finished. You can run it again.`
              : `FINN hasn't read the earnings calls of ${name} yet.`}
          </p>
          <button type="button" className="btn" onClick={start} disabled={state === "starting"}>
            {state === "starting" ? "Starting…" : `Analyse ${name}`}
          </button>
          <p className="small" style={{ marginTop: 12 }}>
            Reads the last six earnings calls filed on NSE and checks each promise against the results the company
            filed later. Takes 10 to 15 minutes; you can leave and come back.
          </p>
        </>
      )}
      {working && (
        <>
          <p>Analysing {name}. This page updates by itself.</p>
          <ol className="steps">
            {STEPS.map((label, i) => (
              <li key={label} data-state={i < at ? "done" : i === at ? "now" : "todo"}>
                <span className="step-dot" aria-hidden /> {label}
              </li>
            ))}
          </ol>
          <p className="small">Usually 10 to 15 minutes. Analyses run one at a time.</p>
        </>
      )}
      {state === "failed" && (
        <p className="notice warn">The analysis stopped before it finished. Try again, or try later if NSE is slow.</p>
      )}
      {message && <p className={`notice${state === "error" || state === "unknown_symbol" ? " warn" : ""}`}>{message}</p>}
    </section>
  );
}
