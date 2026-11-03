// The languages FINN can show. English is the default; the choice is kept in the finn_lang cookie.

export const LANGS = [
  { code: "en", name: "English", english: "English", locale: "en-IN" },
  { code: "hi", name: "हिन्दी", english: "Hindi", locale: "hi-IN" },
  { code: "gu", name: "ગુજરાતી", english: "Gujarati", locale: "gu-IN" },
  { code: "mr", name: "मराठी", english: "Marathi", locale: "mr-IN" },
  { code: "ta", name: "தமிழ்", english: "Tamil", locale: "ta-IN" },
  { code: "te", name: "తెలుగు", english: "Telugu", locale: "te-IN" },
  { code: "bn", name: "বাংলা", english: "Bengali", locale: "bn-IN" },
] as const;

export type Lang = (typeof LANGS)[number]["code"];
export const DEFAULT_LANG: Lang = "en";
export const COOKIE = "finn_lang";

export const isLang = (v: unknown): v is Lang => LANGS.some((l) => l.code === v);

/** Dates in the reader's language, with the digits Indian investors read everywhere (0-9). */
export const localeOf = (lang: Lang) => `${LANGS.find((l) => l.code === lang)!.locale}-u-nu-latn`;
