import type { Verdict } from "./types";

/** The tally, grouped by what a reader can conclude. Labels and meanings live in the dictionaries (lib/i18n). */
export const GROUPS: { key: "checked" | "notDue" | "cantCheck"; verdicts: Verdict[] }[] = [
  { key: "checked", verdicts: ["Kept", "Missed", "Revised", "Dropped"] },
  { key: "notDue", verdicts: ["On track", "Pending"] },
  { key: "cantCheck", verdicts: ["Unverifiable"] },
];
