import { ms } from "@/lib/chart";
import { monthYear } from "@/lib/format";
import type { Dict, Lang } from "@/lib/i18n";
import type { Ledger } from "@/lib/types";

import { VerdictMark, verdictClass } from "./VerdictMark";

const OPEN = new Set(["On track", "Pending", "Revised"]);

/** The next promises still open whose deadline management stated, soonest first. Each opens its row in the ledger below. */
export function ComingUp({ ledger, today, t, lang }: { ledger: Ledger; today: string; t: Dict; lang: Lang }) {
  const next = ledger.promises
    .filter((p) => OPEN.has(p.verdict) && p.due && !p.due_assumed && ms(p.due) >= ms(today))
    .sort((a, b) => a.due!.localeCompare(b.due!))
    .slice(0, 4);
  const c = t.view.coming;
  return (
    <div className="coming">
      <h3 className="sub-title coming-title">{c.title}</h3>
      <p className="section-sub">{c.sub}</p>
      {next.length === 0 ? <p className="small-print">{c.none}</p> : (
        <ol className="coming-list">
          {next.map((p) => (
            <li key={p.id}>
              <a href={`#${p.id}`}>
                <span className="coming-due">{c.due(monthYear(p.due, lang))}</span>
                <span className="coming-what" lang="en">{p.title}</span>
                <span className={`coming-v ${verdictClass(p.verdict)}`}><VerdictMark verdict={p.verdict} /> {t.verdict[p.verdict]}</span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
