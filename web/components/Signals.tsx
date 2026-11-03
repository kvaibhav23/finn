import { dayMonthYear } from "@/lib/format";
import type { Dict, Lang } from "@/lib/i18n";
import { signalText } from "@/lib/sentences";
import type { Signal } from "@/lib/types";

const HREF: Record<Signal["key"], { href: string; key: "promises" | "prices" | "filings" }> = {
  move: { href: "#filings", key: "filings" },
  track: { href: "#promises", key: "promises" },
  price: { href: "#price", key: "prices" },
  delivery: { href: "#price", key: "prices" },
  filings: { href: "#filings", key: "filings" },
};

/** Facts, not a score: each line says what was measured and links to where it comes from. */
export function Signals({ signals, t, lang }: { signals: Signal[]; t: Dict; lang: Lang }) {
  if (!signals.length) return null;
  return (
    <dl className="signals">
      {signals.map((s) => {
        const [text, detail] = signalText(t, lang, s);
        return (
          <div key={s.key} className={`signal${s.key === "move" ? " signal-move" : ""}`}>
            <dt>{t.signal.label[s.key]}</dt>
            <dd>
              <p className="signal-text">{text}</p>
              {detail && <p className="signal-detail">{detail}</p>}
              {s.items && s.items.length > 0 && (
                <ul className="signal-items">
                  {s.items.map((it, i) => (
                    <li key={i}>
                      <a href={it.pdf_url} target="_blank" rel="noreferrer">{t.filings.tag[it.tag] ?? it.tag}</a>
                      {it.date && <span className="chart-sub">, {dayMonthYear(it.date, lang)}</span>}
                    </li>
                  ))}
                </ul>
              )}
              {s.key !== "move" && <a className="signal-src" href={HREF[s.key].href}>{t.signal.source[HREF[s.key].key]}</a>}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
