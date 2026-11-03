// Shapes written by scripts/build_web_data.py. The site only reads these; it never computes a verdict.

export type Verdict = "Kept" | "Missed" | "On track" | "Revised" | "Pending" | "Dropped" | "Unverifiable";

export const VERDICTS: Verdict[] = ["Kept", "Missed", "On track", "Revised", "Pending", "Dropped", "Unverifiable"];

export interface Version {
  quarter: string;
  status: "New" | "Reaffirmed" | "Revised";
  quote: string;
  page: number;
  speaker: string;
  pdf_url: string | null;
  target: string;
  due: string | null;
}

export interface Actual {
  source: "XBRL filing" | "Management, later call";
  value: number | null;
  text: string | null;
  partial: boolean;
  quarters?: string[] | null;
  basis?: string | null;
  definition?: string | null;
  formula?: string | null;
  link?: string | null;
  note?: string | null;
  quote?: string;
  quarter?: string;
  page?: number;
  speaker?: string;
  pdf_url?: string | null;
}

export interface Promise_ {
  id: string;
  metric: string;
  metric_label: string;
  scope: "company" | "segment";
  title: string;
  target: string;
  conditional: boolean;
  due: string | null;
  due_assumed: boolean;
  verdict: Verdict;
  rule: string;
  explanation: string;
  first_quarter: string;
  quote: string;
  speaker: string;
  quarter: string;
  page: number;
  pdf_url: string | null;
  history: Version[];
  searched_later: string[];
  actual: Actual | null;
}

export interface Call {
  quarter: string;
  quarter_end: string;
  pdf_url: string;
}

export interface Ledger {
  symbol: string;
  name: string | null;
  status: "ok" | "no_transcripts" | "failed";
  message: string | null;
  generated_at: string;
  as_of_results?: string | null;
  model?: string;
  cost_inr?: number;
  calls: Call[];
  margin_note?: string | null;
  candidates?: number;
  rejected?: number;
  promises: Promise_[];
}

export interface IndexEntry {
  symbol: string;
  name: string | null;
  status: Ledger["status"];
  generated_at: string;
  as_of_results: string | null;
  calls: number;
  from: string | null;
  to: string | null;
  promises: number;
  counts: Record<Verdict, number>;
  close?: number | null;
  change_pct?: number | null;
  price_as_of?: string | null;
  return_1y?: number | null;
  big_move?: boolean;
}

// Written by finn.market via scripts/build_web_data.py: prices (NSE bhavcopy), results (XBRL), filings (NSE).

export interface PriceStats {
  as_of: string;
  close: number;
  change: number | null;
  change_pct: number | null;
  high_52w: number;
  low_52w: number;
  range_position: number | null;
  return_1y: number | null;
  nifty_return_1y: number | null;
  delivery_20d: number | null;
  delivery_avg: number | null;
  delivery_sessions: number;
}

export interface QuarterFigures {
  quarter: string;
  qe: string;
  revenue_cr: number | null;
  pat_cr: number | null;
  xbrl_url: string | null;
}

export interface Results {
  basis: string;
  bank: boolean;
  latest_quarter: string;
  latest_qe: string;
  xbrl_url: string | null;
  top_line: string;
  ttm_revenue_cr: number | null;
  ttm_pat_cr: number | null;
  ttm_margin_pct: number | null;
  ttm_eps: number | null;
  pe: number | null;
  pe_note: string | null;
  market_cap_cr: number | null;
  revenue_yoy_pct: number | null;
  pat_yoy_pct: number | null;
  net_npa_pct: number | null;
  quarters: QuarterFigures[];
}

export interface Filing {
  date: string | null;
  tag: string;
  worth_a_look: boolean;
  category: string;
  subject: string;
  pdf_url: string;
}

export interface Signal {
  key: "move" | "track" | "price" | "delivery" | "filings";
  state: string;
  facts: Record<string, unknown>;
  items?: { date: string | null; tag: string; pdf_url: string }[];
}

export interface MoveFacts {
  date: string;
  change_pct: number;
  typical_pct: number;
  times: number | null;
  volume_x: number | null;
  biggest_in_year: boolean;
  nifty_change_pct: number | null;
}

export interface Move extends MoveFacts {
  filings: { date: string; tag: string; pdf_url: string }[];
}

export interface MarketDay {
  date: string;
  close: number;
  change_pct: number;
  big: boolean;
  movers: { symbol: string; name: string | null; change_pct: number }[];
}

export interface CallDate {
  quarter: string;
  date: string;
  pdf_url: string | null;
}

/** [date, close, volume, delivery %] */
export type PriceRow = [string, number, number, number | null];

export interface Market {
  symbol: string;
  generated_at: string;
  price: PriceStats | null;
  prices: { source: string; adjusted_for: string[]; rows: PriceRow[] } | null;
  nifty: [string, number][] | null;
  results: Results | null;
  filings: Filing[] | null;
  calls: CallDate[] | null;
  signals: Signal[];
  move: Move | null;
  missing: string[];
}
