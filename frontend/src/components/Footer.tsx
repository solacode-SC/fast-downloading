"use client";

import React from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export function Footer() {
  const { t } = useI18n();

  return (
    <footer className="w-full bg-white dark:bg-[#16161F]">
      <div className="flex w-full flex-wrap items-center justify-between gap-2 border-b-2 border-black bg-zinc-50 px-5 py-3 font-mono text-[11px] font-black uppercase text-black lg:px-8 dark:bg-zinc-900 dark:text-zinc-200">
        <span className="text-zinc-600 dark:text-zinc-400">{t("platformsTitle")}:</span>
        <nav aria-label="Platform downloaders" className="flex flex-wrap items-center gap-3">
          <Link href="/youtube-downloader" className="underline-offset-4 hover:underline">
            {t("platform_youtube_name")} 4K / MP3
          </Link>
          <span aria-hidden="true">·</span>
          <Link href="/twitter-video-downloader" className="underline-offset-4 hover:underline">
            {t("platform_x_name")} MP4
          </Link>
          <span aria-hidden="true">·</span>
          <Link href="/instagram-downloader" className="underline-offset-4 hover:underline">
            {t("platform_instagram_name")} Reels
          </Link>
          <span aria-hidden="true">·</span>
          <Link href="/facebook-downloader" className="underline-offset-4 hover:underline">
            {t("platform_facebook_name")} Watch
          </Link>
        </nav>
      </div>

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
