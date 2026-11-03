// Light or dark. "system" follows the device; the choice is kept in the finn_theme cookie so the server
// renders the right colours on the first paint.

export const THEMES = ["system", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];
export const THEME_COOKIE = "finn_theme";
export const THEME_EVENT = "finn:theme";

export const isTheme = (v: unknown): v is Theme => THEMES.includes(v as Theme);

/** Apply a choice at once, remember it for a year, and tell the other theme controls on the page. */
export function setTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme; else root.dataset.theme = theme;
  document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=31536000; samesite=lax`;
  window.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: theme }));
}

/** The theme in force: the reader's choice, or the device's when they haven't made one. */
export function currentTheme(): Theme {
  const v = document.documentElement.dataset.theme;
  return isTheme(v) ? v : "system";
}

export const isDark = () => {
  const t = currentTheme();
  return t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
};
