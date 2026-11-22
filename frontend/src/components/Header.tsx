"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n, type Locale } from "@/lib/i18n";

type ThemeMode = "system" | "light" | "dark";

export function Header() {
  const { locale, setLocale, t } = useI18n();
  const [theme, setTheme] = useState<ThemeMode>("light");

  useEffect(() => {
    const saved = window.localStorage.getItem("fastdl_theme") as ThemeMode | null;
    if (saved === "light" || saved === "dark" || saved === "system") {
      queueMicrotask(() => setTheme(saved));
    }
  }, []);

  useEffect(() => {
    const apply = (mode: ThemeMode) => {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const isDark = mode === "dark" || (mode === "system" && prefersDark);
      document.documentElement.classList.toggle("dark", isDark);
    };
    apply(theme);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (theme === "system") apply("system");
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const cycleTheme = () => {
    const order: ThemeMode[] = ["light", "dark", "system"];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
    window.localStorage.setItem("fastdl_theme", next);
  };

  const themeLabel =
    theme === "dark" ? t("themeDark") : theme === "light" ? t("themeLight") : t("themeSystem");

  return (
    <header className="sticky top-0 z-40 w-full border-b-2 border-black bg-white dark:bg-[#16161F]">
      <div className="flex w-full flex-wrap items-stretch justify-between">
        {/* Top-left Acid Lime Brand Block */}
        <Link
          href="/"
          className="flex items-center gap-2 border-e-2 border-black bg-brutal-lime px-4 py-3.5 font-mono text-sm font-black uppercase tracking-wider text-black transition hover:bg-[#a6e600] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-black sm:px-7 sm:text-base"
        >
          <span>&lt;/&gt;</span>
          <span>{t("appName")}</span>
        </Link>

        {/* Center Navigation Links (Tablet & Desktop) */}
        <nav
          aria-label="Primary navigation"
          className="hidden items-center gap-6 px-6 font-mono text-xs font-bold uppercase tracking-wider text-black md:flex lg:gap-10 lg:text-sm dark:text-zinc-100"
        >
          <Link href="/" className="hover:underline underline-offset-4">
            {t("navDownloader")}
          </Link>
          <a href="#platforms-strip" className="hover:underline underline-offset-4">
            {t("navPlatforms")}
          </a>
          <a href="#workspace-section" className="hover:underline underline-offset-4">
            {t("navInspector")}
          </a>
          <a href="#pipeline-section" className="hover:underline underline-offset-4">
            {t("navPipeline")}
          </a>
          <Link href="/legal" className="hover:underline underline-offset-4">
            {t("legalLink")}
          </Link>
          <Link href="/dmca" className="hover:underline underline-offset-4">
            {t("dmcaLink")}
          </Link>
        </nav>

        {/* Controls + Right Electric Purple Action Block */}
        <div className="ms-auto flex items-stretch">
          <div className="flex items-center gap-2 border-s-2 border-black px-3 py-2 sm:px-4">
            <label htmlFor="locale-select" className="sr-only">
              Language
            </label>
            <select
              id="locale-select"
              value={locale}
              onChange={(e) => setLocale(e.target.value as Locale)}
              className="border-2 border-black bg-white px-2 py-1 font-mono text-xs font-bold uppercase text-black shadow-brutal-sm focus:outline-none dark:bg-zinc-900 dark:text-zinc-100"
            >
              <option value="en">EN</option>
              <option value="fr">FR</option>
              <option value="ar">العربية</option>
            </select>

            <button
              type="button"
              onClick={cycleTheme}
              aria-label={`Switch theme (current: ${themeLabel})`}
              className="border-2 border-black bg-brutal-pink px-2.5 py-1 font-mono text-xs font-bold uppercase text-black shadow-brutal-sm transition hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none"
            >
              {themeLabel}
            </button>
          </div>

          <Link
            href="/legal"
            className="hidden items-center gap-2 border-s-2 border-black bg-brutal-purple px-5 py-3.5 font-mono text-xs font-black uppercase tracking-wider text-white transition hover:bg-[#684de6] sm:flex lg:px-7"
          >
            <span>{t("publicOnly")}</span>
            <span aria-hidden="true">{locale === "ar" ? "←" : "→"}</span>
          </Link>
        </div>
      </div>

      {/* Mobile Sub-Navigation Strip (<768px) */}
      <nav
        aria-label="Mobile quick navigation"
        className="flex w-full items-center justify-around overflow-x-auto border-t-2 border-black bg-zinc-50 px-2 py-2 font-mono text-[11px] font-black uppercase text-black md:hidden dark:bg-zinc-900 dark:text-zinc-100"
      >
        <Link href="/" className="px-2 py-0.5 hover:underline">
          {t("mobileHome")}
        </Link>
        <a href="#platforms-strip" className="px-2 py-0.5 hover:underline">
          {t("navPlatforms")}
        </a>
        <a href="#workspace-section" className="px-2 py-0.5 hover:underline">
          {t("mobileFormats")}
        </a>
        <Link href="/legal" className="px-2 py-0.5 hover:underline">
          {t("legalLink")}
        </Link>
        <Link href="/dmca" className="px-2 py-0.5 hover:underline">
          {t("dmcaLink")}
        </Link>
      </nav>
    </header>
  );
}
