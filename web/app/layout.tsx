import type { Metadata, Viewport } from "next";
import {
  Instrument_Sans, Noto_Sans_Bengali, Noto_Sans_Devanagari, Noto_Sans_Gujarati, Noto_Sans_Tamil, Noto_Sans_Telugu,
  Source_Serif_4,
} from "next/font/google";
import Link from "next/link";

import { NavLinks } from "@/components/NavLinks";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LangProvider } from "@/lib/i18n/client";
import { LANGS } from "@/lib/i18n/languages";
import { getT, getTheme } from "@/lib/i18n/server";

import "./globals.css";

const ui = Instrument_Sans({ subsets: ["latin"], variable: "--font-ui", display: "swap" });
const quote = Source_Serif_4({ subsets: ["latin"], style: ["italic"], variable: "--font-quote", display: "swap" });
// Indian scripts: listed after Instrument Sans, so the browser downloads one only when the page uses its letters.
const deva = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--font-deva", display: "swap", preload: false });
const gujr = Noto_Sans_Gujarati({ subsets: ["gujarati"], variable: "--font-gujr", display: "swap", preload: false });
const taml = Noto_Sans_Tamil({ subsets: ["tamil"], variable: "--font-taml", display: "swap", preload: false });
const telu = Noto_Sans_Telugu({ subsets: ["telugu"], variable: "--font-telu", display: "swap", preload: false });
const beng = Noto_Sans_Bengali({ subsets: ["bengali"], variable: "--font-beng", display: "swap", preload: false });
const fonts = [ui, quote, deva, gujr, taml, telu, beng].map((f) => f.variable).join(" ");

export const metadata: Metadata = {
  title: { default: "FINN: did management do what they said?", template: "%s | FINN" },
  description:
    "FINN reads the earnings calls of NSE-listed companies, finds every promise that can be checked, and checks it against filed results.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#121a23" },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [{ lang, t }, theme] = await Promise.all([getT(), getTheme()]);
  return (
    <html lang={LANGS.find((l) => l.code === lang)!.locale} className={fonts}
          data-theme={theme === "system" ? undefined : theme}>
      <body>
        <LangProvider lang={lang}>
          <header className="site-head">
            <div className="wrap">
              <Link href="/" className="brand" aria-label={t.nav.home}>
                <span className="brand-name">FINN</span>
                <span className="brand-beta">{t.nav.beta}</span>
              </Link>
              <NavLinks />
              <ThemeToggle />
            </div>
          </header>
          <main className="wrap">{children}</main>
          <footer className="site-foot">
            <div className="wrap">
              <p>{t.footer.disclaimer}</p>
              <p>{t.footer.sources}</p>
            </div>
          </footer>
        </LangProvider>
      </body>
    </html>
  );
}
