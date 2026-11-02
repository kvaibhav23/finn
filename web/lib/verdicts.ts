import type { Verdict } from "./types";

/** What each verdict means, in one plain sentence. Shared by the ledger and the method page. */
export const MEANING: Record<Verdict, string> = {
  Kept: "The deadline has passed and the filed result met the target. Beating a margin or growth band counts; overspending a budget does not.",
  Missed: "The deadline has passed and the result fell short, or management said it was delayed.",
  "On track": "Not due yet, and the results so far already meet the target.",
  Revised: "Not due yet, and a later call changed the number or the deadline.",
  Pending: "Not due yet, or no deadline was given, and there is nothing to judge so far.",
  Dropped: "Never mentioned again in any later call FINN read.",
  Unverifiable: "Due, but there is no filed figure and management never said what happened.",
};

/** The tally, grouped by what a reader can conclude. */
export const GROUPS: { label: string; verdicts: Verdict[] }[] = [
  { label: "Checked", verdicts: ["Kept", "Missed", "Revised", "Dropped"] },
  { label: "Not due yet", verdicts: ["On track", "Pending"] },
  { label: "Couldn't check", verdicts: ["Unverifiable"] },
];
