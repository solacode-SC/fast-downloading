"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n, type Locale } from "@/lib/i18n";

type ThemeMode = "system" | "light" | "dark";

const LOCALE_OPTIONS: { code: Locale; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "fr", label: "FR" },
  { code: "ar", label: "عربي" },
];

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
  const themeIcon = theme === "dark" ? "☾" : theme === "light" ? "☀" : "◐";

  return (
    <header className="sticky top-0 z-40 w-full border-b-2 border-black bg-white dark:bg-[#16161F]">
      <div className="flex w-full flex-nowrap items-stretch justify-between">
        {/* Brand Block */}
        <Link
          href="/"
          className="flex shrink-0 items-center gap-1.5 border-e-2 border-black bg-brutal-lime px-3 py-3 font-mono text-xs font-black uppercase tracking-wider text-black transition hover:bg-[#a6e600] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-black sm:gap-2 sm:px-6 sm:py-3.5 sm:text-base"
        >
          <span dir="ltr">&lt;/&gt;</span>
          <span dir="ltr">{t("appName")}</span>
        </Link>

        {/* Center Navigation Links (Wide Desktop >=1280px so FR/AR never wrap) */}
        <nav
          aria-label="Primary navigation"
          className="hidden items-center gap-5 px-4 font-mono text-xs font-bold uppercase tracking-wider text-black xl:flex 2xl:gap-8 2xl:px-6 2xl:text-sm dark:text-zinc-100"
        >
          <Link href="/" className="whitespace-nowrap underline-offset-4 hover:underline">
            {t("navDownloader")}
          </Link>
          <a
            href="#platforms-strip"
            className="whitespace-nowrap underline-offset-4 hover:underline"
          >
            {t("navPlatforms")}
          </a>
          <a
            href="#workspace-section"
            className="whitespace-nowrap underline-offset-4 hover:underline"
          >
            {t("navInspector")}
          </a>
          <a
            href="#pipeline-section"
            className="whitespace-nowrap underline-offset-4 hover:underline"
          >
            {t("navPipeline")}
          </a>
          <Link href="/legal" className="whitespace-nowrap underline-offset-4 hover:underline">
            {t("legalLink")}
          </Link>
          <Link href="/dmca" className="whitespace-nowrap underline-offset-4 hover:underline">
            {t("dmcaLink")}
          </Link>
        </nav>

        {/* Segmented Language Switcher + Theme Toggle + Public-Only Pill */}
        <div className="ms-auto flex shrink-0 items-stretch">
          <div className="flex items-center gap-1.5 border-s-2 border-black px-2 py-1.5 sm:gap-2.5 sm:px-4 sm:py-2">
            <div
              role="group"
              aria-label="Language selector"
              dir="ltr"
              className="inline-flex items-stretch border-2 border-black bg-white shadow-brutal-sm dark:bg-zinc-900"
            >
              {LOCALE_OPTIONS.map((opt, idx) => {
                const active = locale === opt.code;
                return (
                  <button
                    key={opt.code}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setLocale(opt.code)}
                    className={`px-2 py-1 text-[11px] font-black transition sm:px-2.5 sm:text-xs ${
                      idx > 0 ? "border-l-2 border-black" : ""
                    } ${
                      active
                        ? "bg-brutal-lime text-black"
                        : "bg-white text-black hover:bg-zinc-100 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              onClick={cycleTheme}
              aria-label={`Switch theme (current: ${themeLabel})`}
              className="inline-flex items-center gap-1 border-2 border-black bg-brutal-pink px-2 py-1 font-mono text-[11px] font-bold uppercase text-black shadow-brutal-sm transition hover:translate-y-[1px] hover:shadow-none sm:px-2.5 sm:text-xs"
            >
              <span aria-hidden="true">{themeIcon}</span>
              <span className="hidden xs:inline sm:inline">{themeLabel}</span>
            </button>
          </div>

          <Link
            href="/legal"
            className="hidden items-center gap-2 whitespace-nowrap border-s-2 border-black bg-brutal-purple px-4 py-3.5 font-mono text-xs font-black uppercase tracking-wider text-white transition hover:bg-[#684de6] md:flex lg:px-6"
          >
            <span>{t("publicOnly")}</span>
            <span aria-hidden="true">{locale === "ar" ? "←" : "→"}</span>
          </Link>
        </div>
      </div>

      {/* Sub-Navigation Strip (<1280px: Mobile, Tablet, Compact Laptop) */}
      <nav
        aria-label="Quick navigation"
        className="flex w-full items-center justify-start gap-4 overflow-x-auto border-t-2 border-black bg-zinc-50 px-3 py-2 font-mono text-[11px] font-black uppercase text-black sm:justify-around sm:gap-2 xl:hidden dark:bg-zinc-900 dark:text-zinc-100"
      >
        <Link href="/" className="shrink-0 whitespace-nowrap px-1.5 py-0.5 hover:underline">
          {t("mobileHome")}
        </Link>
        <a
          href="#platforms-strip"
          className="shrink-0 whitespace-nowrap px-1.5 py-0.5 hover:underline"
        >
          {t("navPlatforms")}
        </a>
        <a
          href="#workspace-section"
          className="shrink-0 whitespace-nowrap px-1.5 py-0.5 hover:underline"
        >
          {t("mobileFormats")}
        </a>
        <a
          href="#pipeline-section"
          className="hidden shrink-0 whitespace-nowrap px-1.5 py-0.5 hover:underline sm:inline-block"
        >
          {t("navPipeline")}
        </a>
        <Link href="/legal" className="shrink-0 whitespace-nowrap px-1.5 py-0.5 hover:underline">
          {t("legalLink")}
        </Link>
        <Link href="/dmca" className="shrink-0 whitespace-nowrap px-1.5 py-0.5 hover:underline">
          {t("dmcaLink")}
        </Link>
      </nav>
    </header>
  );
}
