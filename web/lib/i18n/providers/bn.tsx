"use client";

import { Provide } from "../client";
import { bn } from "../bn";

export function LangBn({ children }: { children: React.ReactNode }) {
  return <Provide lang="bn" t={bn}>{children}</Provide>;
}
