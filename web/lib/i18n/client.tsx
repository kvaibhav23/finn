"use client";

import { createContext, useContext } from "react";

import type { Dict } from "./en";
import type { Lang } from "./languages";

const LangContext = createContext<{ lang: Lang; t: Dict } | null>(null);

/** Hands one language's words to every client component below. Each language has its own provider file
 * (providers/<lang>.tsx), so the browser downloads only the language being read, not all seven. */
export function Provide({ lang, t, children }: { lang: Lang; t: Dict; children: React.ReactNode }) {
  return <LangContext.Provider value={{ lang, t }}>{children}</LangContext.Provider>;
}

export function useT(): { lang: Lang; t: Dict } {
  const v = useContext(LangContext);
  if (!v) throw new Error("useT outside LangProvider");
  return v;
}
