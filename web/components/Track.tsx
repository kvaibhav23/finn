import { monthYear, quarter } from "@/lib/format";
import type { Call, Promise_ } from "@/lib/types";

// A promise's life on one line: faint ticks are the calls FINN read; a filled dot is where it was
// first said, a ring where it was repeated, a notch where it was changed; the bar is the deadline,
// coloured only when the outcome was decided. Solid up to the latest results, dashed after.
const W = 260, H = 22, PAD = 6, Y = 11;
const DAY = 86_400_000;

const t = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

export interface Domain { start: number; end: number }

/** One time axis for every row of a ledger, so tracks line up and can be compared down the page. */
export function domainFor(promises: Promise_[], calls: Call[]): Domain {
  const lastCall = t(calls[calls.length - 1].quarter_end);
  const dues = promises.map((p) => (p.due ? Math.min(t(p.due), lastCall + 3 * 365 * DAY) : lastCall));
  return { start: t(calls[0].quarter_end) - 30 * DAY, end: Math.max(lastCall, ...dues) + 45 * DAY };
}

export function Track({ p, calls, asOf, domain }:
  { p: Promise_; calls: Call[]; asOf: string | null | undefined; domain?: Domain }) {
  if (!calls.length) return null;
  const qe = Object.fromEntries(calls.map((c) => [c.quarter, c.quarter_end]));
  const lastCall = t(calls[calls.length - 1].quarter_end);
  const due = p.due ? Math.min(t(p.due), lastCall + 3 * 365 * DAY) : null;
  const { start, end } = domain ?? domainFor([p], calls);
  const x = (ms: number) => PAD + ((ms - start) / (end - start)) * (W - 2 * PAD);

  const marks = p.history
    .filter((v) => qe[v.quarter])
    .map((v) => ({ ...v, x: x(t(qe[v.quarter])) }));
  const firstX = marks[0]?.x ?? PAD;
  const solidTo = x(Math.min(asOf ? t(asOf) : lastCall, due ?? Infinity));
  const dueX = due != null ? x(due) : null;
  const dueColor = p.verdict === "Kept" ? "var(--kept)" : p.verdict === "Missed" ? "var(--missed)" : "var(--ink)";

  const label = [
    ...p.history.map((v) => `${v.status === "New" ? "Said" : v.status} in ${quarter(v.quarter)}`),
    p.due ? `due ${monthYear(p.due)}` : "no deadline",
    p.verdict.toLowerCase(),
  ].join(", ");

  return (
    <svg className="track" width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}
         style={{ maxWidth: W, display: "block" }}>
      {calls.map((c) => (
        <line key={c.quarter} x1={x(t(c.quarter_end))} x2={x(t(c.quarter_end))} y1={Y - 3} y2={Y + 3}
              stroke="var(--rule)" strokeWidth={1} />
      ))}
      {dueX != null && solidTo > firstX && (
        <line x1={firstX} x2={Math.max(firstX, Math.min(solidTo, dueX))} y1={Y} y2={Y} stroke="var(--quiet)" strokeWidth={1.2} />
      )}
      {dueX != null && dueX > Math.max(solidTo, firstX) && (
        <line x1={Math.max(solidTo, firstX)} x2={dueX} y1={Y} y2={Y} stroke="var(--faint)" strokeWidth={1.2}
              strokeDasharray="2 3" />
      )}
      {dueX == null && (
        <line x1={firstX} x2={W - PAD} y1={Y} y2={Y} stroke="var(--faint)" strokeWidth={1.2} strokeDasharray="2 3" />
      )}
      {marks.map((m, i) =>
        m.status === "Revised" ? (
          <line key={i} x1={m.x} x2={m.x} y1={Y - 6} y2={Y + 6} stroke="var(--ink)" strokeWidth={2} />
        ) : m.status === "Reaffirmed" ? (
          <circle key={i} cx={m.x} cy={Y} r={3.4} fill="var(--paper)" stroke="var(--ink)" strokeWidth={1.4} />
        ) : (
          <circle key={i} cx={m.x} cy={Y} r={3.6} fill="var(--ink)" />
        ),
      )}
      {dueX != null && <rect x={dueX - 1.5} y={Y - 7} width={3} height={14} rx={1} fill={dueColor} />}
    </svg>
  );
}
