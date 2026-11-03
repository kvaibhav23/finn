"use client";

import { useEffect, useState } from "react";

import { useT } from "@/lib/i18n/client";
import { THEME_EVENT, isDark, setTheme } from "@/lib/theme";

/** Light or dark in one press. Both icons are drawn; CSS shows the one for the theme in force, so the
 * button is right on the first paint whatever the device prefers. */
export function ThemeToggle() {
  const { t } = useT();
  const [dark, setDark] = useState<boolean | null>(null);

  useEffect(() => {
    const sync = () => setDark(isDark());
    sync();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", sync);
    window.addEventListener(THEME_EVENT, sync);
    return () => {
      mq.removeEventListener("change", sync);
      window.removeEventListener(THEME_EVENT, sync);
    };
  }, []);

  return (
    <button type="button" className="theme-toggle" aria-pressed={dark ?? undefined} aria-label={t.nav.dark}
            title={t.nav.dark} onClick={() => setTheme(isDark() ? "light" : "dark")}>
      <svg className="moon" viewBox="0 0 20 20" width="18" height="18" aria-hidden>
        <path d="M15.5 12.6A6.5 6.5 0 0 1 7.4 4.5a6.5 6.5 0 1 0 8.1 8.1Z" fill="none" stroke="currentColor" strokeWidth="1.5"
              strokeLinejoin="round" />
      </svg>
      <svg className="sun" viewBox="0 0 20 20" width="18" height="18" aria-hidden>
        <circle cx="10" cy="10" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M10 1.8v2.4M10 15.8v2.4M1.8 10h2.4M15.8 10h2.4M4.2 4.2l1.7 1.7M14.1 14.1l1.7 1.7M4.2 15.8l1.7-1.7M14.1 5.9l1.7-1.7"
              stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </button>
  );
}
