import type { Verdict } from "@/lib/types";

// Shape carries the meaning; colour only for the two decided outcomes (Kept, Missed).
export function VerdictMark({ verdict, size = 10 }: { verdict: Verdict; size?: number }) {
  const s = size, h = s / 2;
  const common = { width: s, height: s, viewBox: `0 0 ${s} ${s}`, "aria-hidden": true as const, style: { flex: "none" } };
  switch (verdict) {
    case "Kept":
      return <svg {...common}><circle cx={h} cy={h} r={h - 0.5} fill="var(--kept)" /></svg>;
    case "Missed":
      return <svg {...common}><rect x={0.5} y={0.5} width={s - 1} height={s - 1} rx={1} fill="var(--missed)" /></svg>;
    case "On track":
      return <svg {...common}><circle cx={h} cy={h} r={h - 1} fill="none" stroke="var(--kept)" strokeWidth={1.6} /></svg>;
    case "Revised":
      return (
        <svg {...common}>
          <circle cx={h} cy={h} r={h - 1} fill="none" stroke="var(--ink)" strokeWidth={1.4} />
          <path d={`M${h} 1 A${h - 1} ${h - 1} 0 0 1 ${h} ${s - 1} Z`} fill="var(--ink)" />
        </svg>
      );
    case "Pending":
      return <svg {...common}><circle cx={h} cy={h} r={h - 1} fill="none" stroke="var(--faint)" strokeWidth={1.4} /></svg>;
    case "Dropped":
      return <svg {...common}><line x1={0.5} y1={h} x2={s - 0.5} y2={h} stroke="var(--quiet)" strokeWidth={1.8} /></svg>;
    default:
      return (
        <svg {...common}>
          <circle cx={h} cy={h} r={h - 1} fill="none" stroke="var(--faint)" strokeWidth={1.4} strokeDasharray="1.6 1.6" />
        </svg>
      );
  }
}

export function verdictClass(v: Verdict): string {
  return v === "Kept" ? "v-kept" : v === "Missed" ? "v-missed" : "";
}
