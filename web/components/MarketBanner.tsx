import Link from "next/link";

import { dayMonthYear, displayName, signedPct } from "@/lib/format";
import type { Dict, Lang } from "@/lib/i18n";
import type { MarketDay } from "@/lib/types";

/** One line when the Nifty 50 moves 2% or more (or always, on the Companies page), with the biggest movers. */
export function MarketBanner({ day, t, lang, always = false }: { day: MarketDay; t: Dict; lang: Lang; always?: boolean }) {
  if (!day.big && !always) return null;
  return (
    <aside className={`market${day.big ? " big" : ""}`} aria-label="Nifty 50">
      <p>
        <b>{t.market.banner(signedPct(day.change_pct), dayMonthYear(day.date, lang))}</b>
        {day.movers.length > 0 && (
          <>
            {" "}{t.market.movers}{" "}
            {day.movers.map((m, i) => (
              <span key={m.symbol}>
                {i > 0 && ", "}
                <Link href={`/c/${m.symbol}`}>{displayName(m.name, m.symbol)}</Link>{" "}
                <span className={m.change_pct > 0 ? "up" : m.change_pct < 0 ? "down" : ""}>{signedPct(m.change_pct, 1)}</span>
              </span>
            ))}
          </>
        )}
      </p>
    </aside>
  );
}
