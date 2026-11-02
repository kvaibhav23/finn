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
}
