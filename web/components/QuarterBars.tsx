import { crore, quarter } from "@/lib/format";
import type { QuarterFigures } from "@/lib/types";

// Revenue (grey) and profit (ink) for each filed quarter, on one scale so the margin is visible as the
// gap between the two bars. A loss draws below the line. Values are in the table read by screen readers.
const H = 120, BAR = 12, GAP = 3, GROUP = 2 * BAR + GAP, LABEL = 18;

export function QuarterBars({ quarters, topLine }: { quarters: QuarterFigures[]; topLine: string }) {
  const q = quarters.filter((x) => x.revenue_cr != null);
  if (q.length < 2) return null;
  const max = Math.max(...q.map((x) => Math.max(x.revenue_cr ?? 0, x.pat_cr ?? 0)));
  const min = Math.min(0, ...q.map((x) => x.pat_cr ?? 0));
  const span = max - min || 1;
  const base = (max / span) * (H - LABEL);
  const h = (v: number) => (Math.abs(v) / span) * (H - LABEL);
  const step = 100 / q.length;
  const top = topLine === "total_income" ? "Total income" : "Revenue";

  return (
    <figure className="qbars">
      <figcaption>
        <span className="legend rev" aria-hidden /> {top}
        <span className="legend pat" aria-hidden /> Profit after tax
        <span className="chart-sub">, each quarter, ₹ crore</span>
      </figcaption>
      <svg width="100%" height={H} aria-hidden>
        {q.map((x, i) => {
          const cx = `${step * i + step / 2}%`;
          const rev = x.revenue_cr ?? 0, pat = x.pat_cr ?? 0;
          return (
            <g key={x.qe}>
              <svg x={cx} y={0} overflow="visible">
                <rect x={-GROUP / 2} y={base - h(rev)} width={BAR} height={h(rev)} fill="#c4cbd3" />
                {x.pat_cr != null && (
                  <rect x={-GROUP / 2 + BAR + GAP} y={pat >= 0 ? base - h(pat) : base} width={BAR} height={h(pat)}
                        fill={pat >= 0 ? "var(--ink)" : "var(--missed)"} />
                )}
                <text y={H - 4} textAnchor="middle" className="chart-tick">{quarter(x.quarter).replace(" ", " ")}</text>
              </svg>
            </g>
          );
        })}
        <line x1="0" x2="100%" y1={base} y2={base} stroke="var(--rule)" />
      </svg>
      <table className="visually-hidden">
        <caption>{top} and profit after tax by quarter, ₹ crore</caption>
        <thead><tr><th>Quarter</th><th>{top}</th><th>Profit after tax</th></tr></thead>
        <tbody>
          {q.map((x) => (
            <tr key={x.qe}>
              <td>{quarter(x.quarter)}</td>
              <td>{x.revenue_cr != null ? crore(x.revenue_cr) : "not filed"}</td>
              <td>{x.pat_cr != null ? crore(x.pat_cr) : "not filed"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
