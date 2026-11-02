"use client";

import { useState } from "react";

import { crore, dayMonthYear, quarter, rupees, signedPct } from "@/lib/format";
import type { PriceStats, Results } from "@/lib/types";

interface Item { term: string; value: string; note?: string | null; explain: string }

function items(p: PriceStats | null, r: Results | null): Item[] {
  const out: Item[] = [];
  const top = r?.bank ? "Total income" : "Revenue";
  if (r?.market_cap_cr != null) {
    out.push({ term: "Market cap", value: crore(r.market_cap_cr),
      explain: "What all the company's shares are worth at the last closing price: shares on issue times the price." });
  }
  if (r) {
    out.push({ term: "P/E", value: r.pe != null ? r.pe.toFixed(1) : "n/a", note: r.pe_note,
      explain: "Price divided by the profit per share of the last four quarters. How many years of today's profit the price pays for." });
  }
  if (p) {
    out.push({ term: "52-week range", value: `${rupees(p.low_52w, 0)} to ${rupees(p.high_52w, 0)}`,
      explain: "The lowest and highest price the share traded at over the last year." });
  }
  if (r?.ttm_revenue_cr != null) {
    out.push({ term: `${top}, last 4 quarters`, value: crore(r.ttm_revenue_cr),
      explain: r.bank ? "Interest and other income the bank earned over the last four reported quarters."
        : "Sales from the company's operations over the last four reported quarters." });
  }
  if (r?.ttm_margin_pct != null) {
    out.push({ term: "Profit margin", value: `${r.ttm_margin_pct.toFixed(1)}%`,
      explain: `Profit after tax as a share of ${top.toLowerCase()}, over the last four quarters. Of every ₹100 earned, how much was left as profit.` });
  }
  if (r?.revenue_yoy_pct != null) {
    out.push({ term: `${top} growth`, value: signedPct(r.revenue_yoy_pct), note: `${quarter(r.latest_quarter)} on a year earlier`,
      explain: `${top} in the latest quarter compared with the same quarter a year before, so seasons don't distort it.` });
  }
  if (r?.pat_yoy_pct != null) {
    out.push({ term: "Profit growth", value: signedPct(r.pat_yoy_pct), note: `${quarter(r.latest_quarter)} on a year earlier`,
      explain: "Profit after tax in the latest quarter compared with the same quarter a year before." });
  }
  if (r?.bank && r.net_npa_pct != null) {
    out.push({ term: "Net NPA", value: `${r.net_npa_pct.toFixed(2)}%`,
      explain: "Loans that have stopped paying, after provisions, as a share of all loans. Lower is healthier." });
  }
  if (p?.delivery_20d != null) {
    out.push({ term: "Delivery, 20 days", value: `${p.delivery_20d.toFixed(0)}%`,
      explain: "Share of traded shares that buyers took into their demat accounts, rather than selling the same day." });
  }
  return out;
}

export function KeyNumbers({ price, results }: { price: PriceStats | null; results: Results | null }) {
  const [open, setOpen] = useState<string | null>(null);
  const list = items(price, results);
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
          Results: {results.basis.toLowerCase()} filings up to {quarter(results.latest_quarter)} (quarter ended{" "}
          {dayMonthYear(results.latest_qe)}).{" "}
          {results.xbrl_url && <><a href={results.xbrl_url} target="_blank" rel="noreferrer">Latest XBRL filing</a>.</>}
          {price && <> Price: NSE close on {dayMonthYear(price.as_of)}.</>} Tap a term to see what it means.
        </p>
      )}
    </>
  );
}
