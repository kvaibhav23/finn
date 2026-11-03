"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { useT } from "@/lib/i18n/client";

export function NavLinks() {
  const { t } = useT();
  const path = usePathname();
  const links = [
    { href: "/digest", label: t.nav.digest, on: path === "/digest" },
    { href: "/alerts", label: t.nav.alerts, on: path === "/alerts" },
    { href: "/companies", label: t.nav.companies, on: path === "/companies" || path.startsWith("/c/") },
    { href: "/method", label: t.nav.method, on: path === "/method" },
    { href: "/settings", label: t.nav.settings, on: path === "/settings" },
  ];
  // "/" jumps to the search box on any page, as in most data terminals.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.key !== "/" || e.metaKey || e.ctrlKey || el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      const input = [...document.querySelectorAll<HTMLInputElement>(".search input")].find((i) => i.offsetParent);
      if (!input) return;
      e.preventDefault();
      input.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <nav className="site-nav" aria-label={t.nav.main}>
      {links.map((l) => (
        <Link key={l.href} href={l.href} aria-current={l.on ? "page" : undefined}>{l.label}</Link>
      ))}
    </nav>
  );
}
