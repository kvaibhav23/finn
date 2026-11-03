import { crore, rupees, signedPct } from "@/lib/format";
import type { Dict } from "@/lib/i18n";
import type { Ledger, Market } from "@/lib/types";

type Tone = "up" | "down" | "look" | null;

/** The figures a trader looks for first, in one row under the price, each with a tone where its sign means
 * something. Every value is one already shown, with its source, further down the page. */
export function QuoteBoard({ market, ledger, t }: { market: Market; ledger: Ledger | null; t: Dict }) {
  const p = market.price, r = market.results, k = t.keys, b = t.view.board;
  const cells: { label: string; value: string; note?: string | null; tone?: Tone; href: string }[] = [];

  if (r?.market_cap_cr != null) cells.push({ label: k.marketCap[0], value: crore(r.market_cap_cr, k), href: "#results" });
  if (r) {
    cells.push({ label: k.pe[0], value: r.pe != null ? r.pe.toFixed(1) : k.na,
      note: r.pe_note ? k.peNote[r.pe_note] ?? r.pe_note : null, href: "#results" });
  }
  if (p) {
    cells.push({ label: k.range52[0], value: `${rupees(p.low_52w, 0)} – ${rupees(p.high_52w, 0)}`, href: "#price" });
    if (p.return_1y != null) {
      cells.push({ label: b.year, value: signedPct(p.return_1y), tone: p.return_1y >= 0 ? "up" : "down",
        note: p.nifty_return_1y != null ? b.nifty(signedPct(p.nifty_return_1y)) : null, href: "#price" });
    }
    if (p.delivery_20d != null) {
      cells.push({ label: k.delivery[0], value: `${p.delivery_20d.toFixed(0)}%`,
        note: p.delivery_avg != null ? b.usual(`${p.delivery_avg.toFixed(0)}%`) : null, href: "#price" });
    }
  }
  if (ledger?.status === "ok") {
    const kept = ledger.promises.filter((x) => x.verdict === "Kept").length;
    const decided = kept + ledger.promises.filter((x) => x.verdict === "Missed").length;
    cells.push({ label: b.kept, value: b.keptOf(kept, decided), href: "#promises" });
  }
  if (market.filings) {
    const look = market.filings.filter((x) => x.worth_a_look).length;
    cells.push({ label: b.look, value: String(look), tone: look ? "look" : null, href: "#filings" });
  }
  if (!cells.length) return null;

  return (
    <ul className="board" aria-label={b.aria}>
      {cells.map((c) => (
        <li key={c.label}>
          <a href={c.href} className={`board-cell${c.tone ? ` tone-${c.tone}` : ""}`}>
            <span className="board-label">{c.label}</span>
            <span className="board-value">{c.value}</span>
            {c.note && <span className="board-note">{c.note}</span>}
          </a>
        </li>
      ))}
    </ul>
  );
}
