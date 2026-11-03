"use client";

import { Provide } from "../client";
import { gu } from "../gu";

export function LangGu({ children }: { children: React.ReactNode }) {
  return <Provide lang="gu" t={gu}>{children}</Provide>;
}
