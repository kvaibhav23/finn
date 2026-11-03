import { DEFAULT_LANG, localeOf, type Lang } from "./i18n/languages.ts";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const utc = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00Z`);
const fmt = (lang: Lang, o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat(localeOf(lang), { ...o, timeZone: "UTC" });

/** "Q4FY25" -> "Q4 FY25" */
export function quarter(q: string | null | undefined): string {
  return q ? q.replace(/^(Q\d)(FY\d+)$/, "$1 $2") : "";
}

/** "2026-03-31" -> "Mar 2026" (month name in the reader's language) */
export function monthYear(iso: string | null | undefined, lang: Lang = DEFAULT_LANG): string {
  if (!iso) return "";
  if (lang === "en") {
    const [y, m] = iso.split("-");
    return `${MONTHS[Number(m) - 1]} ${y}`;
  }
  return fmt(lang, { month: "short", year: "numeric" }).format(utc(iso));
}

/** "2026-03-31" -> "Mar" (for chart axes) */
export function monthShort(iso: string, lang: Lang = DEFAULT_LANG): string {
  return lang === "en" ? MONTHS[Number(iso.slice(5, 7)) - 1] : fmt(lang, { month: "short" }).format(utc(iso));
}

/** Opens the transcript PDF at the quoted page (supported by browser PDF viewers). */
export function pageLink(pdf: string | null, page: number): string | null {
  return pdf ? `${pdf}#page=${page}` : null;
}

export function displayName(name: string | null, symbol: string): string {
  return name ? name.replace(/\s+Limited$/i, "").replace(/\s+Ltd\.?$/i, "") : symbol;
}

/** 3412.5 -> "₹3,412.50" (Indian digit grouping) */
export function rupees(n: number, digits = 2): string {
  return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

/** Crore amounts the way Indian investors read them: "₹12.34 lakh cr" from 1,00,000 crore, else "₹45,230 cr". */
export function crore(n: number, words: { lakhCr: string; cr: string } = { lakhCr: "lakh cr", cr: "cr" }): string {
  if (Math.abs(n) >= 100_000) return `₹${(n / 100_000).toLocaleString("en-IN", { maximumFractionDigits: 2 })} ${words.lakhCr}`;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: Math.abs(n) >= 100 ? 0 : 1 })} ${words.cr}`;
}

/** 4.26 -> "+4.3%", -1.2 -> "−1.2%" (a true minus sign) */
export function signedPct(n: number, digits = 1): string {
  const s = Math.abs(n).toFixed(digits);
  return n > 0 ? `+${s}%` : n < 0 ? `−${s}%` : `${s}%`;
}

/** "2026-10-30" -> "30 Oct 2026" (month name in the reader's language) */
export function dayMonthYear(iso: string | null | undefined, lang: Lang = DEFAULT_LANG): string {
  if (!iso) return "";
  if (lang === "en") {
    const [y, m, d] = iso.split("-");
    return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
  }
  return fmt(lang, { day: "numeric", month: "short", year: "numeric" }).format(utc(iso));
}

/** Share counts the Indian way: "1.95 crore", "19.5 lakh", else "45,230". */
export function shares(n: number, words: { crore: string; lakh: string } = { crore: "crore", lakh: "lakh" }): string {
  if (n >= 1e7) return `${(n / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 2 })} ${words.crore}`;
  if (n >= 1e5) return `${(n / 1e5).toLocaleString("en-IN", { maximumFractionDigits: 1 })} ${words.lakh}`;
  return n.toLocaleString("en-IN");
}
