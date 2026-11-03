"use client";

import { Provide } from "../client";
import { en } from "../en";

export function LangEn({ children }: { children: React.ReactNode }) {
  return <Provide lang="en" t={en}>{children}</Provide>;
}
