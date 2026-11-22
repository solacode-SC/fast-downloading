"use client";

import Link from "next/link";
import React from "react";
import { useI18n } from "@/lib/i18n";

export default function DmcaPage() {
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
            {t("dmcaPageTitle")}
          </h1>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <section className="border-2 border-black bg-white p-6 shadow-brutal lg:col-span-7 dark:bg-[#16161F]">
            <h2 className="font-sans text-lg font-black uppercase text-black dark:text-zinc-100">
              {t("dmcaSec1Title")}
            </h2>
            <p className="mt-2 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
              {t("dmcaSec1Body")}
            </p>
            <ul className="mt-4 list-disc space-y-1.5 ps-5 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
              <li>{t("dmcaItem1")}</li>
              <li>{t("dmcaItem2")}</li>
              <li>{t("dmcaItem3")}</li>
              <li>{t("dmcaItem4")}</li>
            </ul>
          </section>

          <section className="flex flex-col justify-between border-2 border-black bg-brutal-pink p-6 text-black shadow-brutal lg:col-span-5">
            <div className="space-y-2">
              <h2 className="font-sans text-lg font-black uppercase">{t("dmcaContactTitle")}</h2>
              <p className="font-mono text-xs sm:text-sm">{t("dmcaContactBody")}</p>
            </div>
            <p
              dir="ltr"
              className="mt-6 inline-block self-start border-2 border-black bg-white px-4 py-2 font-mono text-sm font-black shadow-brutal-sm"
            >
              dmca@example.com
            </p>
          </section>
        </div>
      </div>
    </article>
  );
}
