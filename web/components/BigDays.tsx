"use client";

import { biggestDays } from "@/lib/chart";
import { dayMonthYear, signedPct } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { PriceRow } from "@/lib/types";

export const AT_EVENT = "finn:at";

/** The year's largest one-day moves. Choosing one moves the price chart's marker to that day. */
export function BigDays({ rows, nifty }: { rows: PriceRow[]; nifty: [string, number][] | null }) {
  const { t, lang } = useT();
  const days = biggestDays(rows, nifty, 5);
  if (!days.length) return null;
  const d = t.view.days;
  const show = (date: string) => {
    window.dispatchEvent(new CustomEvent(AT_EVENT, { detail: date }));
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.querySelector(".chart")?.scrollIntoView({ block: "start", behavior: still ? "auto" : "smooth" });
  };
  return (
    <div className="bigdays-wrap">
      <h2 className="sub-title">{d.title}</h2>
      <p className="section-sub">{d.sub}</p>
      <ol className="bigdays">
        {days.map((x) => (
          <li key={x.date}>
            <button type="button" onClick={() => show(x.date)}>
              <span className={`bd-pct ${x.pct > 0 ? "up" : "down"}`}>{signedPct(x.pct)}</span>
              <span className="bd-date">{dayMonthYear(x.date, lang)}</span>
              <span className="chart-sub">{x.nifty != null ? d.nifty(signedPct(x.nifty)) : d.noNifty}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
