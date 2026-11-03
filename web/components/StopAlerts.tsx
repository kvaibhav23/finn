"use client";

import { useState } from "react";

import { useT } from "@/lib/i18n/client";

/** The page an email's unsubscribe link opens: one button, so mail scanners opening the link change nothing. */
export function StopAlerts({ token, symbol }: { token: string; symbol: string | null }) {
  const { t } = useT();
  const [state, setState] = useState<"ask" | "busy" | "stopped" | "stopped_one" | "invalid">("ask");

  const stop = async (one: boolean) => {
    setState("busy");
    const q = `t=${encodeURIComponent(token)}${one && symbol ? `&s=${encodeURIComponent(symbol)}` : ""}`;
    try {
      const r = await fetch(`/api/alerts/unsubscribe?${q}`, { method: "POST" });
      const s = (await r.json()) as { state: "stopped" | "stopped_one" | "invalid" };
      setState(s.state);
    } catch {
      setState("invalid");
    }
  };

  if (state === "stopped") return <p className="notice" role="status">{t.settings.stopped}</p>;
  if (state === "stopped_one") return <p className="notice" role="status">{t.settings.stoppedOne(symbol ?? "")}</p>;
  if (state === "invalid") return <p className="notice warn" role="status">{t.settings.invalid}</p>;
  return (
    <div className="notice">
      <p style={{ marginTop: 0 }}><b>{t.settings.stopAsk}</b></p>
      <div className="alerts-actions">
        {symbol && <button type="button" className="btn" disabled={state === "busy"} onClick={() => stop(true)}>{t.settings.stopOne(symbol)}</button>}
        <button type="button" className={symbol ? "btn-plain" : "btn"} disabled={state === "busy"} onClick={() => stop(false)}>
          {state === "busy" ? t.settings.stopping : t.settings.stopAll}
        </button>
      </div>
    </div>
  );
}
