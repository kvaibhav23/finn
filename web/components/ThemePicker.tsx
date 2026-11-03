"use client";

import { useEffect, useState } from "react";

import { useT } from "@/lib/i18n/client";
import { THEMES, THEME_EVENT, type Theme, currentTheme, setTheme } from "@/lib/theme";

/** Match the device, or always light, or always dark. Kept in step with the header button. */
export function ThemePicker({ initial }: { initial: Theme }) {
  const { t } = useT();
  const [theme, set] = useState<Theme>(initial);

  useEffect(() => {
    const sync = () => set(currentTheme());
    window.addEventListener(THEME_EVENT, sync);
    return () => window.removeEventListener(THEME_EVENT, sync);
  }, []);

  return (
    <fieldset className="langs">
      <legend className="visually-hidden">{t.settings.theme}</legend>
      {THEMES.map((x) => (
        <label key={x} className={`lang${theme === x ? " on" : ""}`}>
          <input type="radio" name="theme" checked={theme === x} onChange={() => setTheme(x)} />
          <span className="lang-name">{t.settings.themes[x]}</span>
        </label>
      ))}
    </fieldset>
  );
}
