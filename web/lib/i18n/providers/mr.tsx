"use client";

import { Provide } from "../client";
import { mr } from "../mr";

export function LangMr({ children }: { children: React.ReactNode }) {
  return <Provide lang="mr" t={mr}>{children}</Provide>;
}
