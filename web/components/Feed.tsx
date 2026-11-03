"use client";

import Link from "next/link";
import { useState } from "react";

import { dayMonthYear } from "@/lib/format";
import { useT } from "@/lib/i18n/client";

export type FeedKind = "move" | "look" | "results" | "order" | "dividend";
export interface FeedItem {
  date: string; symbol: string; kind: FeedKind; tag: string; text: string; href: string; english: boolean;
  tone: "up" | "down" | null;
}

const KINDS: FeedKind[] = ["move", "look", "results", "order", "dividend"];

/** What changed across every company FINN covers, newest first, with one press to narrow it to a kind. */
export function Feed({ items, days }: { items: FeedItem[]; days: number }) {
  const { t, lang } = useT();
  const f = t.home.feed;
  const [kind, setKind] = useState<FeedKind | "all">("all");
  const present = KINDS.filter((k) => items.some((x) => x.kind === k));
  const shown = items.filter((x) => kind === "all" || x.kind === kind).slice(0, 12);

  return (
    <div className="feed">
      <h2 className="section-title">{f.title}</h2>
      <p className="section-sub">{f.sub(days)}</p>
      <div className="seg seg-wrap" role="group" aria-label={f.title}>
        <button type="button" aria-pressed={kind === "all"} onClick={() => setKind("all")}>{f.kinds.all} {items.length}</button>
        {present.map((k) => (
          <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>
            {f.kinds[k]} {items.filter((x) => x.kind === k).length}
          </button>
        ))}
      </div>
      {shown.length === 0 ? <p className="empty">{f.empty}</p> : (
        <ol className="feed-list">
          {shown.map((x, i) => (
            <li key={i} className={`feed-item k-${x.kind}`}>
              <span className="feed-date">{dayMonthYear(x.date, lang)}</span>
              <Link href={`/c/${x.symbol}`} className="feed-sym">{x.symbol}</Link>
              <span className="feed-body">
                <span className={`feed-tag${x.tone ? ` ${x.tone}` : ""}`}>{x.tag}</span>
                <a href={x.href} className="feed-text" lang={x.english ? "en" : undefined}
                   {...(x.href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})}>{x.text}</a>
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
