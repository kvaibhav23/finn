import { dayMonthYear } from "@/lib/format";
import type { Signal } from "@/lib/types";

const SOURCE: Record<Signal["source"], { href: string; text: string }> = {
  promises: { href: "#promises", text: "See the promises" },
  prices: { href: "#overview", text: "NSE daily prices" },
  filings: { href: "#filings", text: "See the filings" },
};

/** Facts, not a score: each line says what was measured and links to where it comes from. */
export function Signals({ signals }: { signals: Signal[] }) {
  if (!signals.length) return null;
  return (
    <dl className="signals">
      {signals.map((s) => (
        <div key={s.key} className="signal">
          <dt>{s.label}</dt>
          <dd>
            <p className="signal-text">{s.text}</p>
            {s.detail && <p className="signal-detail">{s.detail}</p>}
            {s.items && s.items.length > 0 && (
              <ul className="signal-items">
                {s.items.map((it, i) => (
                  <li key={i}>
                    <a href={it.pdf_url} target="_blank" rel="noreferrer">{it.tag}</a>
                    {it.date && <span className="chart-sub">, {dayMonthYear(it.date)}</span>}
                  </li>
                ))}
              </ul>
            )}
            <a className="signal-src" href={SOURCE[s.source].href}>{SOURCE[s.source].text}</a>
          </dd>
        </div>
      ))}
    </dl>
  );
}
