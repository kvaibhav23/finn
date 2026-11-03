"use client";

import { Provide } from "../client";
import { hi } from "../hi";

export function LangHi({ children }: { children: React.ReactNode }) {
  return <Provide lang="hi" t={hi}>{children}</Provide>;
}
