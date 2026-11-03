import { crore, quarter, signedPct } from "@/lib/format";
import type { Dict } from "@/lib/i18n";
import type { ResultsCardData } from "@/lib/types";

// A quarter's four headline figures (finn.market.stats.results_card) against the quarter before and the same quarter
// a year earlier. Plain markup with the words passed in, so the company page (server) and the digest (client) share it.
export function ResultsCard({ card, t, compact = false }: { card: ResultsCardData; t: Dict; compact?: boolean }) {
  const r = t.results;
  const pct = (n: number | null) => n == null
    ? <span className="rc-dash" aria-label="—">—</span>
    : <span className={n > 0 ? "up" : n < 0 ? "down" : ""}>{signedPct(n)}</span>;
  const dashed = card.rows.some((x) => x.now != null && !x.note && (x.qoq == null || x.yoy == null));
  return (
    <figure className={`rcard${compact ? " compact" : ""}`} aria-label={r.aria(quarter(card.quarter))}>
      {!compact && (
        <figcaption className="section-sub">
          {r.sub(quarter(card.quarter), r.basis[card.basis ?? ""] ?? card.basis ?? "")}{" "}
          {card.xbrl_url && <a href={card.xbrl_url} target="_blank" rel="noreferrer">{r.xbrl}</a>}
        </figcaption>
      )}
      <table>
        <thead>
          <tr>
            <th scope="col"><span className="visually-hidden">{quarter(card.quarter)}</span></th>
            <th scope="col" className="num">{quarter(card.quarter)}</th>
            <th scope="col" className="num">{card.prev_quarter ? r.vs(quarter(card.prev_quarter)) : r.lastQ}</th>
            <th scope="col" className="num">{card.year_quarter ? r.vs(quarter(card.year_quarter)) : r.yearAgo}</th>
          </tr>
        </thead>
        <tbody>
          {card.rows.map((x) => (
            <tr key={x.key}>
              <th scope="row">{r.row[x.key]}</th>
              {x.note ? (
                <td className="num rc-note" colSpan={3}>{r.bank}</td>
              ) : (
                <>
                  <td className="num rc-now">{x.now == null ? "—" : crore(x.now, t.keys)}</td>
                  <td className="num">{pct(x.qoq)}</td>
                  <td className="num">{pct(x.yoy)}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {!compact && (
        <p className="small-print">{r.ebitda}{dashed ? ` ${r.dash}` : ""}</p>
      )}
      {compact && card.xbrl_url && (
        <p className="small-print">
          {r.sub(quarter(card.quarter), r.basis[card.basis ?? ""] ?? card.basis ?? "")}{" "}
          <a href={card.xbrl_url} target="_blank" rel="noreferrer">{r.xbrl}</a>
        </p>
      )}
    </figure>
  );
}
