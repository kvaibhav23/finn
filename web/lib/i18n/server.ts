import { cookies } from "next/headers";

import { dict } from "./index";
import { DEFAULT_THEME, THEME_COOKIE, type Theme, isTheme } from "../theme";

import { COOKIE, DEFAULT_LANG, isLang, type Lang } from "./languages";

/** The reader's language from the finn_lang cookie (set on the Settings page). */
export async function getLang(): Promise<Lang> {
  const v = (await cookies()).get(COOKIE)?.value;
  return isLang(v) ? v : DEFAULT_LANG;
}

export async function getT() {
  const lang = await getLang();
  return { lang, t: dict(lang) };
}

/** The reader's light/dark choice from the finn_theme cookie. Light until they choose otherwise. */
export async function getTheme(): Promise<Theme> {
  const v = (await cookies()).get(THEME_COOKIE)?.value;
  return isTheme(v) ? v : DEFAULT_THEME;
}
