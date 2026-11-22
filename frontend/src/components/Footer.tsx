"use client";

import React from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export function Footer() {
  const { t } = useI18n();

  return (
    <footer className="w-full bg-white dark:bg-[#16161F]">
      <div className="flex w-full flex-col items-stretch justify-between md:flex-row">
        <div className="flex items-center border-b-2 border-black bg-brutal-lime px-5 py-4 font-mono text-xs font-black uppercase tracking-wider text-black md:border-b-0 md:border-e-2 lg:px-8">
          <span>
            &lt;/&gt; {t("appName")} {t("engineFooter")}
          </span>
        </div>

        <div className="flex flex-1 items-center px-5 py-4 font-mono text-xs leading-relaxed text-zinc-800 lg:px-8 dark:text-zinc-300">
          {t("legalNotice")}
        </div>

        <nav
          aria-label="Legal navigation"
          className="flex flex-wrap items-center gap-2.5 border-t-2 border-black px-5 py-4 md:border-t-0 md:border-s-2 lg:px-8"
        >
          <Link
            href="/legal"
            className="border-2 border-black bg-white px-3 py-1.5 font-mono text-xs font-bold uppercase text-black shadow-brutal-sm transition hover:bg-brutal-lime"
          >
            {t("legalLink")}
          </Link>
          <Link
            href="/dmca"
            className="border-2 border-black bg-brutal-pink px-3 py-1.5 font-mono text-xs font-bold uppercase text-black shadow-brutal-sm transition hover:bg-brutal-lime"
          >
            {t("dmcaLink")}
          </Link>
        </nav>
      </div>
    </footer>
  );
}
