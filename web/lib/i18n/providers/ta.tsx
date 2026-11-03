"use client";

import { Provide } from "../client";
import { ta } from "../ta";

export function LangTa({ children }: { children: React.ReactNode }) {
  return <Provide lang="ta" t={ta}>{children}</Provide>;
}
