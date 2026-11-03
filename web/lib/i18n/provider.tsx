"use client";

import dynamic from "next/dynamic";

import type { Lang } from "./languages";

type P = React.ComponentType<{ children: React.ReactNode }>;

// One chunk per language, loaded on demand: the page only fetches the words of the language being read (the
// server marks that chunk for preloading), instead of all seven on every visit.
const PROVIDERS: Record<Lang, P> = {
  en: dynamic(() => import("./providers/en").then((m) => m.LangEn)),
  hi: dynamic(() => import("./providers/hi").then((m) => m.LangHi)),
  gu: dynamic(() => import("./providers/gu").then((m) => m.LangGu)),
  mr: dynamic(() => import("./providers/mr").then((m) => m.LangMr)),
  ta: dynamic(() => import("./providers/ta").then((m) => m.LangTa)),
  te: dynamic(() => import("./providers/te").then((m) => m.LangTe)),
  bn: dynamic(() => import("./providers/bn").then((m) => m.LangBn)),
};

export function LangProvider({ lang, children }: { lang: Lang; children: React.ReactNode }) {
  const C = PROVIDERS[lang];
  return <C>{children}</C>;
}
