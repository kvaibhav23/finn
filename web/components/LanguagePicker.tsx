"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { useT } from "@/lib/i18n/client";
import { COOKIE, LANGS, type Lang } from "@/lib/i18n/languages";

/** Each language is written in its own script, so anyone can find theirs whatever is showing now. */
export function LanguagePicker() {
  const { lang, t } = useT();
  const router = useRouter();
  const [saved, setSaved] = useState(false);
  const [pending, start] = useTransition();

  const choose = (code: Lang) => {
    document.cookie = `${COOKIE}=${code}; path=/; max-age=31536000; samesite=lax`;
    setSaved(true);
    start(() => router.refresh());
  };

  return (
    <fieldset className="langs" aria-busy={pending}>
      <legend className="visually-hidden">{t.settings.language}</legend>
      {LANGS.map((l) => (
        <label key={l.code} className={`lang${lang === l.code ? " on" : ""}`} lang={l.locale}>
          <input type="radio" name="lang" checked={lang === l.code} onChange={() => choose(l.code)} />
          <span className="lang-name">{l.name}</span>
          {l.code !== "en" && <span className="lang-en" lang="en">{l.english}</span>}
        </label>
      ))}
      {saved && !pending && <span className="saved" role="status">{t.settings.saved}</span>}
    </fieldset>
  );
}
