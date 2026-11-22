"use client";

import Link from "next/link";
import React from "react";
import { useI18n } from "@/lib/i18n";

export default function LegalPage() {
  const { t } = useI18n();

  return (
    <article className="bg-grid-paper flex min-h-[calc(100vh-120px)] w-full flex-col justify-between border-b-2 border-black p-5 sm:p-10 lg:p-16">
      <div className="w-full space-y-8">
        <div className="space-y-3">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 border-2 border-black bg-brutal-lime px-3.5 py-1.5 font-mono text-xs font-black uppercase text-black shadow-brutal-sm"
          >
            {t("backToDownloader")}
          </Link>
          <h1 className="font-sans text-3xl font-black uppercase tracking-tight text-black sm:text-5xl dark:text-zinc-50">
            {t("legalPageTitle")}
          </h1>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <section className="border-2 border-black bg-white p-6 shadow-brutal dark:bg-[#16161F]">
            <span className="inline-block border-2 border-black bg-brutal-lime px-2 py-0.5 font-mono text-xs font-black text-black">
              01
            </span>
            <h2 className="mt-3 font-sans text-lg font-black uppercase text-black dark:text-zinc-100">
              {t("legalSec1Title")}
            </h2>
            <p className="mt-2 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
              {t("legalSec1Body")}
            </p>
          </section>

          <section className="border-2 border-black bg-white p-6 shadow-brutal dark:bg-[#16161F]">
            <span className="inline-block border-2 border-black bg-brutal-pink px-2 py-0.5 font-mono text-xs font-black text-black">
              02
            </span>
            <h2 className="mt-3 font-sans text-lg font-black uppercase text-black dark:text-zinc-100">
              {t("legalSec2Title")}
            </h2>
            <ul className="mt-2 list-disc space-y-1.5 ps-5 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
              <li>{t("legalSec2Item1")}</li>
              <li>{t("legalSec2Item2")}</li>
              <li>{t("legalSec2Item3")}</li>
            </ul>
          </section>

          <section className="border-2 border-black bg-white p-6 shadow-brutal dark:bg-[#16161F]">
            <span className="inline-block border-2 border-black bg-brutal-purple px-2 py-0.5 font-mono text-xs font-black text-white">
              03
            </span>
            <h2 className="mt-3 font-sans text-lg font-black uppercase text-black dark:text-zinc-100">
              {t("legalSec3Title")}
            </h2>
            <p className="mt-2 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
              {t("legalSec3Body")}
            </p>
          </section>
        </div>
      </div>
    </article>
  );
}
