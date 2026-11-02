import type { Metadata, Viewport } from "next";
import { Instrument_Sans, Source_Serif_4 } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const ui = Instrument_Sans({ subsets: ["latin"], variable: "--font-ui", display: "swap" });
const quote = Source_Serif_4({ subsets: ["latin"], style: ["italic"], variable: "--font-quote", display: "swap" });

export const metadata: Metadata = {
  title: { default: "FINN: did management do what they said?", template: "%s | FINN" },
  description:
    "FINN reads the earnings calls of NSE-listed companies, finds every promise that can be checked, and checks it against filed results.",
};

export const viewport: Viewport = { themeColor: "#ffffff" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${ui.variable} ${quote.variable}`}>
      <body>
        <header className="site-head">
          <div className="wrap">
            <Link href="/" className="brand" aria-label="FINN home">
              <span className="brand-name">FINN</span>
              <span className="brand-beta">Beta</span>
            </Link>
            <nav className="site-nav" aria-label="Main">
              <Link href="/">Companies</Link>
              <Link href="/method">How it works</Link>
            </nav>
          </div>
        </header>
        <main className="wrap">{children}</main>
        <footer className="site-foot">
          <div className="wrap">
            <p>
              Beta. Verdicts are produced by automated rules from public NSE filings and are not investment advice.
              Every claim links to its source; check it before relying on it.
            </p>
            <p>Transcripts and results: National Stock Exchange of India filings.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
