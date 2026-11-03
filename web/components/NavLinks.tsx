"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useT } from "@/lib/i18n/client";

export function NavLinks() {
  const { t } = useT();
  const path = usePathname();
  const links = [
    { href: "/companies", label: t.nav.companies, on: path === "/companies" || path.startsWith("/c/") },
    { href: "/method", label: t.nav.method, on: path === "/method" },
    { href: "/settings", label: t.nav.settings, on: path === "/settings" },
  ];
  return (
    <nav className="site-nav" aria-label={t.nav.main}>
      {links.map((l) => (
        <Link key={l.href} href={l.href} aria-current={l.on ? "page" : undefined}>{l.label}</Link>
      ))}
    </nav>
  );
}
