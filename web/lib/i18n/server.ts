import { cookies } from "next/headers";

import { dict } from "./index";
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
