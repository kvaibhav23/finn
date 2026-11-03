import { bn } from "./bn";
import { en, type Dict } from "./en";
import { gu } from "./gu";
import { hi } from "./hi";
import { DEFAULT_LANG, isLang, type Lang } from "./languages";
import { mr } from "./mr";
import { ta } from "./ta";
import { te } from "./te";

export type { Dict } from "./en";
export * from "./languages";

const DICTS: Record<Lang, Dict> = { en, hi, gu, mr, ta, te, bn };

export const dict = (lang: string | undefined | null): Dict => DICTS[isLang(lang) ? lang : DEFAULT_LANG];
