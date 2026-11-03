"use client";

import { useRef, useState } from "react";

import { dayMonthYear } from "@/lib/format";
import { useT } from "@/lib/i18n/client";

const W = 600;

/** A close-by-close line with its area, green when the period rose and red when it fell. Pointing at it (or the
 * arrow keys) reads out any day's close. */
export function AreaChart({ series, height = 150, label }: { series: [string, number][]; height?: number; label: string }) {
  const { lang } = useT();
  const box = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<number | null>(null);
  if (series.length < 2) return null;

  const vals = series.map((r) => r[1]);
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const x = (i: number) => (i / (series.length - 1)) * W;
  const y = (v: number) => 6 + (1 - (v - lo) / span) * (height - 12);
  const line = series.map((r, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(r[1]).toFixed(1)}`).join("");
  const dir = vals[vals.length - 1] >= vals[0] ? "up" : "down";
  const point = at != null ? series[at] : null;

  const move = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r) return;
    setAt(Math.round(Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * (series.length - 1)));
  };
  const key = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const d = (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1);
    setAt((i) => Math.max(0, Math.min(series.length - 1, (i ?? series.length - 1) + d)));
  };

  return (
    <div className="area">
      <p className="area-read" aria-live="polite">
        {point ? <><b>{point[1].toLocaleString("en-IN", { maximumFractionDigits: 2 })}</b> {dayMonthYear(point[0], lang)}</> : " "}
      </p>
      <div ref={box} className="area-box" tabIndex={0} role="img" aria-label={label} onKeyDown={key}
           onPointerMove={(e) => move(e.clientX)} onPointerDown={(e) => move(e.clientX)}
           onPointerLeave={() => setAt(null)} onBlur={() => setAt(null)}>
        <svg viewBox={`0 0 ${W} ${height}`} width="100%" height={height} preserveAspectRatio="none" aria-hidden>
          <path d={`${line}L${W},${height}L0,${height}Z`} className={`pc-area ${dir}`} />
          <path d={line} className={`pc-line ${dir}`} vectorEffect="non-scaling-stroke" />
        </svg>
        {at != null && (
          <span className="area-cross" style={{ left: `${(at / (series.length - 1)) * 100}%` }}>
            <span className={`area-dot ${dir}`} style={{ top: y(series[at][1]) }} />
          </span>
        )}
      </div>
    </div>
  );
}
