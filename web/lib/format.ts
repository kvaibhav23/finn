const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "Q4FY25" -> "Q4 FY25" */
export function quarter(q: string | null | undefined): string {
  return q ? q.replace(/^(Q\d)(FY\d+)$/, "$1 $2") : "";
}

/** "2026-03-31" -> "Mar 2026" */
export function monthYear(iso: string | null | undefined): string {
  if (!iso) return "";
  const [y, m] = iso.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
}

/** Opens the transcript PDF at the quoted page (supported by browser PDF viewers). */
export function pageLink(pdf: string | null, page: number): string | null {
  return pdf ? `${pdf}#page=${page}` : null;
}

export function displayName(name: string | null, symbol: string): string {
  return name ? name.replace(/\s+Limited$/i, "").replace(/\s+Ltd\.?$/i, "") : symbol;
}
