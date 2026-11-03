"use client";

import { Provide } from "../client";
import { te } from "../te";

export function LangTe({ children }: { children: React.ReactNode }) {
  return <Provide lang="te" t={te}>{children}</Provide>;
}
