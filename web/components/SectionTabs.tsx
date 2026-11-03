"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { useT } from "@/lib/i18n/client";

export interface Tab { id: string; label: string; count?: number }

const TAB_EVENT = "finn:tab";

/** Switch the company page to a section from anywhere on it (the chart's call marks use this). */
export function openTab(id: string) {
  window.dispatchEvent(new CustomEvent(TAB_EVENT, { detail: id }));
}

const typing = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

/** One section of the company page at a time. Every section has its own address (/c/TCS#price), a link to
 * anything inside a section (a promise) opens that section, and keys 1–n switch sections. */
export function SectionTabs({ tabs, panels }: { tabs: Tab[]; panels: React.ReactNode[] }) {
  const { t } = useT();
  const [active, setActive] = useState(tabs[0].id);
  const top = useRef<HTMLDivElement>(null);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  // Bring the section's start into view when switching from further down the page.
  const show = useCallback((id: string, scroll: boolean) => {
    setActive(id);
    if (!scroll || !top.current) return;
    const y = top.current.getBoundingClientRect().top + window.scrollY;
    if (window.scrollY > y) window.scrollTo({ top: y });
  }, []);

  const fromHash = useCallback((scroll: boolean) => {
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (!id) return;
    if (tabs.some((x) => x.id === id)) return show(id, scroll);
    const panel = document.getElementById(id)?.closest<HTMLElement>("[data-tab]");
    if (panel?.dataset.tab) setActive(panel.dataset.tab);
  }, [tabs, show]);

  // Before child effects run, so a promise link can scroll to a row that is already visible.
  useLayoutEffect(() => { fromHash(false); }, [fromHash]);

  useEffect(() => {
    const onHash = () => fromHash(true);
    const onTab = (e: Event) => show((e as CustomEvent<string>).detail, true);
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) return;
      const n = Number(e.key);
      if (Number.isInteger(n) && n >= 1 && n <= tabs.length) {
        e.preventDefault();
        select(tabs[n - 1].id);
      }
    };
    window.addEventListener("hashchange", onHash);
    window.addEventListener(TAB_EVENT, onTab);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener(TAB_EVENT, onTab);
      window.removeEventListener("keydown", onKey);
    };
  });

  // On a phone the tab bar scrolls sideways: keep the chosen tab fully in it (sideways only, never the page).
  useEffect(() => {
    const b = buttons.current[tabs.findIndex((x) => x.id === active)], list = b?.parentElement;
    if (!b || !list) return;
    if (b.offsetLeft < list.scrollLeft) list.scrollLeft = b.offsetLeft;
    else if (b.offsetLeft + b.offsetWidth > list.scrollLeft + list.clientWidth) {
      list.scrollLeft = b.offsetLeft + b.offsetWidth - list.clientWidth;
    }
  }, [active, tabs]);

  const select = (id: string) => {
    history.replaceState(null, "", `#${id}`);
    show(id, true);
  };

  const onListKey = (e: React.KeyboardEvent, i: number) => {
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1
      : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : null;
    if (next == null) return;
    e.preventDefault();
    const j = (next + tabs.length) % tabs.length;
    select(tabs[j].id);
    buttons.current[j]?.focus();
  };

  return (
    <>
      <div ref={top} />
      <div className="tabs" role="tablist" aria-label={t.view.sections}>
        {tabs.map((x, i) => (
          <button key={x.id} ref={(el) => { buttons.current[i] = el; }} type="button" role="tab" id={`tab-${x.id}`}
                  aria-selected={active === x.id} aria-controls={x.id} tabIndex={active === x.id ? 0 : -1}
                  onClick={() => select(x.id)} onKeyDown={(e) => onListKey(e, i)}>
            <kbd aria-hidden>{i + 1}</kbd>
            {x.label}
            {x.count != null && <span className="n">{x.count}</span>}
          </button>
        ))}
        <span className="tabs-keys">{t.view.keys(tabs.length)}</span>
      </div>
      {tabs.map((x, i) => (
        <section key={x.id} id={x.id} data-tab={x.id} role="tabpanel" aria-labelledby={`tab-${x.id}`}
                 hidden={active !== x.id} className="panel">
          {panels[i]}
        </section>
      ))}
    </>
  );
}
