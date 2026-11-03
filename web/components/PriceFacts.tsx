import { periodReturns } from "@/lib/chart";
import { dayMonthYear, rupees, signedPct } from "@/lib/format";
import type { Dict, Lang } from "@/lib/i18n";
import type { PriceRow, PriceStats } from "@/lib/types";

/** Where today's close sits between the year's low and high. */
export function RangeBar({ p, t }: { p: PriceStats; t: Dict }) {
  const span = p.high_52w - p.low_52w;
  const at = span > 0 ? Math.min(1, Math.max(0, (p.close - p.low_52w) / span)) : 0.5;
  return (
    <figure className="range">
      <figcaption className="sub-title range-title">{t.keys.range52[0]}</figcaption>
      <div className="range-bar" aria-hidden>
        <span className="range-fill" style={{ width: `${at * 100}%` }} />
        <span className="range-dot" style={{ left: `${at * 100}%` }}>
          <span className="range-now">{rupees(p.close)}</span>
        </span>
      </div>
      <div className="range-ends">
        <span>{t.view.range.low} <b>{rupees(p.low_52w)}</b></span>
        <span>{t.view.range.high} <b>{rupees(p.high_52w)}</b></span>
      </div>
      <p className="small-print">{t.view.range.at(`${Math.round(at * 100)}%`)}</p>
    </figure>
  );
}

/** Returns over standard periods next to the Nifty 50's over the same two dates. */
export function Returns({ rows, nifty, symbol, t, lang }:
  { rows: PriceRow[]; nifty: [string, number][] | null; symbol: string; t: Dict; lang: Lang }) {
  const list = periodReturns(rows, nifty);
  if (!list.length) return null;
  const r = t.view.returns;
  const sign = (n: number) => (n > 0 ? "up" : n < 0 ? "down" : "");
  return (
    <div className="returns-wrap">
      <h2 className="sub-title">{r.title}</h2>
      <p className="section-sub">{r.sub}</p>
      <table className="returns">
        <thead>
          <tr>
            <th scope="col">{r.period}</th>
            <th scope="col" className="num">{symbol}</th>
            <th scope="col" className="num">{r.nifty}</th>
            <th scope="col" className="num">{r.gap}</th>
          </tr>
        </thead>
        <tbody>
          {list.map((x) => {
            const gap = x.nifty != null ? x.stock - x.nifty : null;
            return (
              <tr key={x.key}>
                <th scope="row">{r.label[x.key]}<span className="chart-sub"> {r.from(dayMonthYear(x.from, lang))}</span></th>
                <td className={`num ${sign(x.stock)}`}>{signedPct(x.stock)}</td>
                <td className="num">{x.nifty != null ? signedPct(x.nifty) : ""}</td>
                <td className="num">
                  {gap != null && (
                    <span className="gap">
                      <span className="gap-bar" aria-hidden>
                        <span className={sign(gap)} style={{ width: `${Math.min(50, Math.abs(gap) * 1.5)}%` }} />
                      </span>
                      {r.pts(signedPct(gap).replace("%", ""))}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Daily delivery % for the sessions that have it, with the average as a line. */
export function DeliveryBars({ rows, t, lang }: { rows: PriceRow[]; t: Dict; lang: Lang }) {
  const d = rows.filter((r) => r[3] != null) as [string, number, number, number][];
  if (d.length < 10) return null;
  const W = 600, H = 90;
  const avg = d.reduce((s, r) => s + r[3], 0) / d.length;
  const w = W / d.length;
  const y = (v: number) => H - (v / 100) * H;
  return (
    <figure className="delivery">
      <figcaption>
        <h2 className="sub-title">{t.view.delivery.title}</h2>
        <p className="section-sub">{t.view.delivery.sub(`${avg.toFixed(0)}%`, d.length)}</p>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" role="img"
           aria-label={t.view.delivery.sub(`${avg.toFixed(0)}%`, d.length)}>
        {d.map((r, i) => (
          <rect key={r[0]} x={i * w + 0.5} width={Math.max(1, w - 1)} y={y(r[3])} height={H - y(r[3])}
                className={r[3] >= avg ? "above" : ""}>
            <title>{t.view.delivery.bar(dayMonthYear(r[0], lang), `${r[3].toFixed(0)}%`)}</title>
          </rect>
        ))}
        <line x1={0} x2={W} y1={y(avg)} y2={y(avg)} className="avg" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="range-ends chart-sub">
        <span>{dayMonthYear(d[0][0], lang)}</span>
        <span>{dayMonthYear(d.at(-1)![0], lang)}</span>
      </div>
    </figure>
  );
}
