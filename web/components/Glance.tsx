import { ms, thin } from "@/lib/chart";
import { crore, dayMonthYear, monthYear, quarter, signedPct } from "@/lib/format";
import type { Dict, Lang } from "@/lib/i18n";
import type { Ledger, Market } from "@/lib/types";

import { Sparkline } from "./Sparkline";

const OPEN = new Set(["On track", "Pending", "Revised"]);

/** Four panels, one per section, each a headline fact and a small picture of it. Each opens its section. */
export function Glance({ market, ledger, days, t, lang }:
  { market: Market | null; ledger: Ledger | null; days: number; t: Dict; lang: Lang }) {
  const g = t.view.tile;
  const tiles: React.ReactNode[] = [];
  const p = market?.price ?? null;
  const rows = market?.prices?.rows ?? [];

  if (p && rows.length > 1) {
    const year = p.return_1y;
    tiles.push(
      <Tile key="price" href="#price" label={t.view.tabs.price}
            head={year != null ? g.priceYear(year >= 0, `${Math.abs(year).toFixed(1)}%`)
              : g.priceShort(signedPct((rows.at(-1)![1] / rows[0][1] - 1) * 100), dayMonthYear(rows[0][0], lang))}
            sub={p.nifty_return_1y != null ? g.priceNifty(signedPct(p.nifty_return_1y)) : null}>
        <Sparkline values={thin(rows.map((r) => r[1]))} width={240} height={48} />
      </Tile>,
    );
  }

  const r = market?.results ?? null;
  if (market) {
    const q = r?.quarters.filter((x) => x.revenue_cr != null) ?? [];
    tiles.push(
      <Tile key="results" href="#results" label={t.view.tabs.results}
            head={r && r.revenue_yoy_pct != null && r.pat_yoy_pct != null
              ? g.results(r.bank, signedPct(r.revenue_yoy_pct), signedPct(r.pat_yoy_pct)) : g.noResults}
            sub={r ? [r.revenue_yoy_pct != null ? g.resultsSub(quarter(r.latest_quarter)) : null,
              r.pe != null && r.market_cap_cr != null ? g.pe(r.pe.toFixed(1), crore(r.market_cap_cr, t.keys)) : null]
              .filter(Boolean).join(". ") : null}>
        {q.length > 1 && <MiniBars values={q.map((x) => x.pat_cr ?? 0)} />}
      </Tile>,
    );
  }

  const ok = ledger?.status === "ok";
  const c = (v: string) => ledger?.promises.filter((x) => x.verdict === v).length ?? 0;
  const kept = c("Kept"), missed = c("Missed"), decided = kept + missed;
  const open = ledger?.promises.filter((x) => OPEN.has(x.verdict)) ?? [];
  const today = p?.as_of ?? new Date().toISOString().slice(0, 10);
  const next = open.filter((x) => !x.due_assumed).map((x) => x.due)
    .filter((d): d is string => !!d && ms(d) >= ms(today)).sort()[0] ?? null;
  const total = ledger?.promises.length ?? 0;
  tiles.push(
    <Tile key="promises" href="#promises" label={t.view.tabs.promises}
          head={!ok ? g.notRead : decided >= 3 ? g.kept(kept, decided) : g.few(decided)}
          sub={ok ? g.open(open.length, next ? monthYear(next, lang) : null) : null}>
      {ok && total > 0 && (
        <span className="mix tile-mix" aria-hidden>
          <span className="kept" style={{ width: `${(kept / total) * 100}%` }} />
          <span className="missed" style={{ width: `${(missed / total) * 100}%` }} />
          <span className="open" style={{ width: `${(open.length / total) * 100}%` }} />
        </span>
      )}
    </Tile>,
  );

  const f = market?.filings ?? null;
  if (f) {
    const look = f.filter((x) => x.worth_a_look);
    const kinds = [...new Set(look.map((x) => (t.filings.tag[x.tag] ?? x.tag).toLowerCase()))].join(", ");
    const latest = f[0];
    tiles.push(
      <Tile key="filings" href="#filings" label={t.view.tabs.filings}
            head={look.length ? g.look(look.length, kinds) : g.clear}
            sub={[g.count(f.length, days), latest ? g.latest(t.filings.tag[latest.tag] ?? latest.tag, dayMonthYear(latest.date, lang)) : null]
              .filter(Boolean).join(", ")}>
        {p && f.length > 0 && <Dots filings={f} end={p.as_of} days={days} />}
      </Tile>,
    );
  }

  if (!tiles.length) return null;
  return (
    <div className="glance-wrap">
      <h2 className="sub-title glance-title">{t.view.glance}</h2>
      <p className="section-sub">{t.view.glanceSub}</p>
      <div className="glance">{tiles}</div>
    </div>
  );
}

function Tile({ href, label, head, sub, children }:
  { href: string; label: string; head: string; sub: string | null; children?: React.ReactNode }) {
  return (
    <a className="tile" href={href}>
      <span className="tile-label">{label}</span>
      <span className="tile-head">{head}</span>
      {sub && <span className="tile-sub">{sub}</span>}
      {children && <span className="tile-pic">{children}</span>}
    </a>
  );
}

/** Profit by quarter as small bars; a loss hangs below the line. */
function MiniBars({ values }: { values: number[] }) {
  const W = 240, H = 48, gap = 4;
  const hi = Math.max(0, ...values), lo = Math.min(0, ...values);
  const span = hi - lo || 1;
  const base = (hi / span) * H;
  const w = (W - gap * (values.length - 1)) / values.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} preserveAspectRatio="none" aria-hidden focusable="false" className="minibars">
      {values.map((v, i) => (
        <rect key={i} x={i * (w + gap)} width={w} y={v >= 0 ? base - (v / span) * H : base}
              height={Math.max(1, (Math.abs(v) / span) * H)} className={v < 0 ? "loss" : i === values.length - 1 ? "last" : ""} />
      ))}
    </svg>
  );
}

/** Filings over the window as marks on a line; worth-a-look filings stand taller. */
function Dots({ filings, end, days }: { filings: Market["filings"] & object; end: string; days: number }) {
  const W = 240, H = 48;
  const t1 = ms(end), t0 = t1 - days * 86_400_000;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} preserveAspectRatio="none" aria-hidden focusable="false" className="dots">
      <line x1={0} x2={W} y1={H - 1} y2={H - 1} />
      {filings.filter((x) => x.date && ms(x.date) >= t0).map((x, i) => {
        const cx = ((ms(x.date!) - t0) / (t1 - t0)) * (W - 2) + 1;
        return <line key={i} x1={cx} x2={cx} y1={x.worth_a_look ? 6 : H - 18} y2={H - 1} className={x.worth_a_look ? "look" : ""} />;
      })}
    </svg>
  );
}
