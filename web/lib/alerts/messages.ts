// The words of each alert, in the subscriber's language, built from the event's facts (tested with node --test).

import { dayMonthYear } from "../format.ts";
import type { Dict } from "../i18n/en.ts";
import type { Lang } from "../i18n/languages.ts";

export interface AlertEvent {
  id: string;
  symbol: string;
  kind: "move" | "flag" | "results" | "ledger";
  date: string;
  facts: Record<string, unknown>;
}

export interface Message { subject: string; text: string; link: string; filing: string | null }

const pct = (n: number) => `${Math.abs(n).toFixed(1)}%`;

export function message(t: Dict, lang: Lang, e: AlertEvent, name: string, site: string): Message {
  const link = `${site}/c/${encodeURIComponent(e.symbol)}`;
  const date = dayMonthYear(e.date, lang);
  const f = e.facts;
  switch (e.kind) {
    case "move": {
      const c = Number(f.change_pct), up = c >= 0;
      const times = typeof f.times === "number" ? f.times.toFixed(1) : null;
      return { subject: t.msg.subjectMove(e.symbol, up, pct(c)), link: `${link}#overview`, filing: null,
        text: t.msg.move(name, up, pct(c), date, times, Boolean(f.biggest_in_year)) };
    }
    case "flag": {
      const tag = t.filings.tag[String(f.tag)] ?? String(f.tag);
      return { subject: t.msg.subjectFlag(e.symbol, tag), text: t.msg.flag(name, tag, date), link: `${link}#filings`,
        filing: String(f.pdf_url ?? "") || null };
    }
    case "results":
      return { subject: t.msg.subjectResults(e.symbol), text: t.msg.results(name, date), link: `${link}#overview`,
        filing: String(f.pdf_url ?? "") || null };
    case "ledger": {
      const kept = Number(f.Kept ?? 0), decided = kept + Number(f.Missed ?? 0);
      return { subject: t.msg.subjectLedger(e.symbol), text: t.msg.ledger(name, kept, decided), link: `${link}#promises`,
        filing: null };
    }
  }
}

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** A plain email: no images, no tracking, the facts and the links. */
export function emailHtml(t: Dict, m: Message, symbol: string, stopOne: string, stopAll: string): string {
  return `<!doctype html><html><body style="margin:0;padding:24px;font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;color:#1d2733">
<p style="margin:0 0 4px;font-weight:600;letter-spacing:.06em">FINN</p>
<p style="font-size:17px;margin:16px 0">${esc(m.text)}</p>
<p><a href="${esc(m.link)}" style="color:#2350b8">${esc(t.msg.open)}</a>${m.filing ? ` &nbsp; <a href="${esc(m.filing)}" style="color:#2350b8">${esc(t.msg.filing)}</a>` : ""}</p>
<p style="color:#66717e;font-size:13px;margin-top:28px">${esc(t.msg.notAdvice)} ${esc(t.msg.why(symbol))}<br>
<a href="${esc(stopOne)}" style="color:#66717e">${esc(t.msg.unsubscribeOne(symbol))}</a> &nbsp; <a href="${esc(stopAll)}" style="color:#66717e">${esc(t.msg.unsubscribeAll)}</a></p>
</body></html>`;
}

export function emailText(t: Dict, m: Message, symbol: string, stopOne: string, stopAll: string): string {
  return [m.text, "", `${t.msg.open}: ${m.link}`, m.filing ? `${t.msg.filing}: ${m.filing}` : "", "",
    `${t.msg.notAdvice} ${t.msg.why(symbol)}`, `${t.msg.unsubscribeOne(symbol)}: ${stopOne}`,
    `${t.msg.unsubscribeAll}: ${stopAll}`].filter((l, i, a) => l || a[i - 1]).join("\n");
}

export function confirmHtml(t: Dict, symbol: string, url: string): string {
  return `<!doctype html><html><body style="margin:0;padding:24px;font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;color:#1d2733">
<p style="margin:0 0 4px;font-weight:600;letter-spacing:.06em">FINN</p>
<p style="margin:16px 0">${esc(t.msg.confirmBody(symbol))}</p>
<p><a href="${esc(url)}" style="display:inline-block;background:#2350b8;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:600">${esc(t.msg.confirmButton)}</a></p>
<p style="color:#66717e;font-size:13px">${esc(url)}</p>
</body></html>`;
}
