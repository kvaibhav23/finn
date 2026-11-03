"use client";

import { useState } from "react";

import { crore, dayMonthYear, quarter, rupees, signedPct } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { Dict } from "@/lib/i18n";
import type { PriceStats, Results } from "@/lib/types";

interface Item { term: string; value: string; note?: string | null; explain: string }

function items(t: Dict, p: PriceStats | null, r: Results | null): Item[] {
  const out: Item[] = [];
  const k = t.keys;
  const add = ([term, explain]: string[], value: string, note?: string | null) => out.push({ term, explain, value, note });
  const cr = (n: number) => crore(n, k);
  if (r?.market_cap_cr != null) add(k.marketCap, cr(r.market_cap_cr));
  if (r) add(k.pe, r.pe != null ? r.pe.toFixed(1) : k.na, r.pe_note ? k.peNote[r.pe_note] ?? r.pe_note : null);
  if (p) add(k.range52, `${rupees(p.low_52w, 0)} ${k.to} ${rupees(p.high_52w, 0)}`);
  if (r?.ttm_revenue_cr != null) add(r.bank ? k.income4 : k.revenue4, cr(r.ttm_revenue_cr));
  if (r?.ttm_margin_pct != null) add(k.margin, `${r.ttm_margin_pct.toFixed(1)}%`);
  if (r?.revenue_yoy_pct != null) {
    add(r.bank ? k.incomeGrowth : k.revGrowth, signedPct(r.revenue_yoy_pct), k.onYear(quarter(r.latest_quarter)));
  }
  if (r?.pat_yoy_pct != null) add(k.patGrowth, signedPct(r.pat_yoy_pct), k.onYear(quarter(r.latest_quarter)));
  if (r?.bank && r.net_npa_pct != null) add(k.npa, `${r.net_npa_pct.toFixed(2)}%`);
  if (p?.delivery_20d != null) add(k.delivery, `${p.delivery_20d.toFixed(0)}%`);
  return out;
}

export function KeyNumbers({ price, results }: { price: PriceStats | null; results: Results | null }) {
  const { t, lang } = useT();
  const [open, setOpen] = useState<string | null>(null);
  const list = items(t, price, results);
  if (!list.length) return null;
  return (
    <>
      <dl className="keys">
        {list.map((it) => (
          <div key={it.term} className="key">
            <dt>
              <button type="button" className="term" aria-expanded={open === it.term}
                      onClick={() => setOpen(open === it.term ? null : it.term)}>
                {it.term}
              </button>
            </dt>
            <dd>
              <span className="key-value">{it.value}</span>
              {it.note && <span className="key-note">{it.note}</span>}
              {open === it.term && <span className="key-explain">{it.explain}</span>}
            </dd>
          </div>
        ))}
      </dl>
      {results && (
        <p className="small-print">
          {t.keys.results(t.keys.basis[results.basis] ?? results.basis, quarter(results.latest_quarter),
            dayMonthYear(results.latest_qe, lang))}{" "}
          {results.xbrl_url && <><a href={results.xbrl_url} target="_blank" rel="noreferrer">{t.keys.xbrl}</a>.</>}
          {price && t.keys.price(dayMonthYear(price.as_of, lang))} {t.keys.tap}
        </p>
      )}
    </>
  );
}
