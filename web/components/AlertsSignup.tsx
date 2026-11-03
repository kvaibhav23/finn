"use client";

import { useId, useState } from "react";

import { useT } from "@/lib/i18n/client";

const EVENTS = ["move", "flag", "results", "ledger"] as const;
type Channel = "email" | "whatsapp";
type Done = "check_email" | "whatsapp_on" | "added";

export function AlertsSignup({ symbol, name, channels }:
  { symbol: string; name: string; channels: { email: boolean; whatsapp: boolean } }) {
  const { t, lang } = useT();
  const id = useId();
  const a = t.alerts;
  const available = (["email", "whatsapp"] as Channel[]).filter((c) => channels[c]);
  const [open, setOpen] = useState(false);
  const [channel, setChannel] = useState<Channel>(available[0] ?? "email");
  const [address, setAddress] = useState("");
  const [events, setEvents] = useState<Set<string>>(new Set(EVENTS));
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Done | null>(null);
  const [sentTo, setSentTo] = useState("");

  if (!open) {
    return (
      <p className="alerts-open">
        <button type="button" className="btn-quiet" onClick={() => setOpen(true)} aria-expanded={false}>
          <BellIcon /> {a.open}
        </button>
      </p>
    );
  }

  if (done) {
    return (
      <div className="alerts" role="status">
        <p>{done === "check_email" ? a.checkEmail(sentTo) : done === "whatsapp_on" ? a.whatsappOn : a.added(name)}</p>
      </div>
    );
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!events.size) return setError(a.errors.events);
    if (!consent) return setError(a.errors.consent);
    setBusy(true);
    try {
      const website = (new FormData(e.currentTarget).get("website") as string) || "";
      const r = await fetch("/api/alerts/subscribe", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, channel, address, events: [...events], consent, lang, website }),
      });
      const s = (await r.json()) as { state: Done | "error"; error?: string };
      if (s.state === "error") setError(a.errors[s.error ?? "error"] ?? a.errors.error);
      else { setSentTo(address.trim()); setDone(s.state); }
    } catch {
      setError(a.errors.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="alerts" onSubmit={submit} noValidate>
      <h2 className="alerts-title">{a.title(name)}</h2>
      {!available.length ? (
        <p className="small-print">{a.off}</p>
      ) : (
        <>
          {available.length > 1 && (
            <fieldset className="alerts-row">
              <legend>{a.channel}</legend>
              {available.map((c) => (
                <label key={c} className="check">
                  <input type="radio" name={`${id}-ch`} checked={channel === c} onChange={() => { setChannel(c); setAddress(""); }} />
                  {a[c]}
                </label>
              ))}
            </fieldset>
          )}
          <label className="alerts-field">
            <span>{channel === "email" ? a.emailLabel : a.phoneLabel}</span>
            <input type={channel === "email" ? "email" : "tel"} inputMode={channel === "email" ? "email" : "numeric"}
                   autoComplete={channel === "email" ? "email" : "tel-national"} required value={address}
                   placeholder={channel === "email" ? "name@example.com" : "98765 43210"}
                   onChange={(e) => setAddress(e.target.value)} />
            {channel === "whatsapp" && <span className="small-print">{a.phoneHint}</span>}
          </label>
          <fieldset className="alerts-row alerts-events">
            <legend>{a.events}</legend>
            {EVENTS.map((ev) => (
              <label key={ev} className="check">
                <input type="checkbox" checked={events.has(ev)} onChange={(e) => {
                  const n = new Set(events);
                  if (e.target.checked) n.add(ev); else n.delete(ev);
                  setEvents(n);
                }} />
                {a.event[ev]}
              </label>
            ))}
          </fieldset>
          <input type="text" name="website" tabIndex={-1} autoComplete="off" className="visually-hidden" aria-hidden />
          <label className="check alerts-consent">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            {a.consent(name)}
          </label>
          {error && <p className="notice warn" role="alert">{error}</p>}
          <div className="alerts-actions">
            <button type="submit" className="btn" disabled={busy}>{busy ? a.sending : a.submit}</button>
            <button type="button" className="btn-plain" onClick={() => setOpen(false)}>{a.cancel}</button>
          </div>
          <p className="small-print">{a.privacy}</p>
        </>
      )}
    </form>
  );
}

function BellIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden style={{ flex: "none" }}>
      <path d="M8 1.5a4 4 0 0 0-4 4v2.7L2.7 11h10.6L12 8.2V5.5a4 4 0 0 0-4-4zM6.3 12.5a1.8 1.8 0 0 0 3.4 0"
            fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
