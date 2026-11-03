"use client";

import { createContext, useContext } from "react";

import { dict, type Dict } from "./index";
import { DEFAULT_LANG, type Lang } from "./languages";

const LangContext = createContext<Lang>(DEFAULT_LANG);

export function LangProvider({ lang, children }: { lang: Lang; children: React.ReactNode }) {
  return <LangContext.Provider value={lang}>{children}</LangContext.Provider>;
}

export function useT(): { lang: Lang; t: Dict } {
  const lang = useContext(LangContext);
  return { lang, t: dict(lang) };
}
