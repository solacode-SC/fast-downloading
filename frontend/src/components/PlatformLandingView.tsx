import Link from "next/link";
import React from "react";
import type { Platform } from "@/lib/api";
import { PLATFORM_SEO } from "@/lib/seo";

interface PlatformLandingViewProps {
  platform: Platform;
}

export function PlatformLandingView({ platform }: PlatformLandingViewProps) {
  const cfg = PLATFORM_SEO[platform];
  const otherPlatforms = (["youtube", "x", "instagram", "facebook"] as const).filter(
    (p) => p !== platform
  );

  return (
    <article
      aria-label={`${cfg.name} Video Downloader Guide`}
      className="w-full border-b-2 border-black bg-white dark:bg-[#12121A]"
    >
      {/* Overview & Supported Formats */}
      <section className="grid w-full grid-cols-1 border-b-2 border-black lg:grid-cols-12">
        <div className="border-b-2 border-black bg-brutal-lime p-6 sm:p-8 lg:col-span-5 lg:border-b-0 lg:border-e-2 xl:p-12">
          <span className="inline-block border-2 border-black bg-black px-2.5 py-1 font-mono text-[11px] font-black uppercase text-brutal-lime">
            FASTDL // {cfg.name.toUpperCase()} GUIDE
          </span>
          <h2 className="mt-4 font-sans text-2xl font-black uppercase leading-tight text-black sm:text-3xl">
            HOW TO DOWNLOAD {cfg.name.toUpperCase()} VIDEOS FAST & FREE
          </h2>
          <p className="mt-3 font-mono text-xs leading-relaxed text-black/85 sm:text-sm">
            {cfg.summary}
          </p>
          <div className="mt-6">
            <Link
              href="/"
              className="inline-flex items-center gap-2 border-2 border-black bg-white px-4 py-2.5 font-mono text-xs font-black uppercase text-black shadow-brutal-sm transition hover:bg-brutal-pink"
            >
              <span>ALL-IN-ONE DOWNLOADER</span>
              <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 divide-y-2 divide-black sm:grid-cols-2 sm:divide-y-0 lg:col-span-7">
          {cfg.supportedFormats.map((fmt, idx) => (
            <div
              key={fmt.label}
              className={`flex flex-col justify-between bg-white p-5 sm:p-6 dark:bg-[#16161F] ${
                idx < 2 ? "sm:border-b-2 sm:border-black" : ""
              } ${idx % 2 === 0 ? "sm:border-e-2 sm:border-black" : ""}`}
            >
              <div>
                <span className="inline-block border-2 border-black bg-brutal-pink px-2 py-0.5 font-mono text-[10px] font-black uppercase text-black">
                  FORMAT 0{idx + 1}
                </span>
                <h3 className="mt-3 font-sans text-base font-black uppercase text-black dark:text-zinc-100">
                  {fmt.label}
                </h3>
                <p className="mt-1.5 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
                  {fmt.detail}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 3-Step Guide + Key Highlights */}
      <section className="grid w-full grid-cols-1 border-b-2 border-black lg:grid-cols-12">
        <div className="border-b-2 border-black bg-zinc-50 p-6 sm:p-8 lg:col-span-6 lg:border-b-0 lg:border-e-2 xl:p-12 dark:bg-[#16161F]">
          <h2 className="font-sans text-xl font-black uppercase text-black sm:text-2xl dark:text-zinc-100">
            3 STEPS TO SAVE {cfg.name.toUpperCase()} MEDIA
          </h2>
          <ol className="mt-5 space-y-4">
            {cfg.steps.map((step, idx) => (
              <li
                key={step.title}
                className="flex items-start gap-3.5 border-2 border-black bg-white p-4 shadow-brutal-sm dark:bg-zinc-900"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center border-2 border-black bg-brutal-lime font-mono text-xs font-black text-black">
                  0{idx + 1}
                </span>
                <div>
                  <h3 className="font-sans text-sm font-black uppercase text-black sm:text-base dark:text-zinc-100">
                    {step.title}
                  </h3>
                  <p className="mt-1 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
                    {step.text}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="bg-white p-6 sm:p-8 lg:col-span-6 xl:p-12 dark:bg-[#12121A]">
          <h2 className="font-sans text-xl font-black uppercase text-black sm:text-2xl dark:text-zinc-100">
            WHY USE FASTDL FOR {cfg.name.toUpperCase()}?
          </h2>
          <div className="mt-5 space-y-4">
            {cfg.highlights.map((item) => (
              <div
                key={item.title}
                className="border-2 border-black bg-zinc-50 p-4 shadow-brutal-sm dark:bg-zinc-900"
              >
                <h3 className="font-sans text-sm font-black uppercase text-black sm:text-base dark:text-zinc-100">
                  {item.title}
                </h3>
                <p className="mt-1 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
                  {item.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Platform FAQ + Cross-Links */}
      <section className="grid w-full grid-cols-1 lg:grid-cols-12">
        <div className="divide-y-2 divide-black border-b-2 border-black lg:col-span-8 lg:border-b-0 lg:border-e-2">
          {cfg.faqs.map((faq, idx) => (
            <details
              key={faq.q}
              open={idx === 0}
              className="group bg-white p-5 sm:p-6 dark:bg-[#16161F]"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-sans text-sm font-black uppercase text-black sm:text-base dark:text-zinc-100">
                <span>{faq.q}</span>
                <span
                  aria-hidden="true"
                  className="flex h-7 w-7 shrink-0 items-center justify-center border-2 border-black bg-brutal-pink font-mono text-xs font-black text-black transition group-open:rotate-45 group-open:bg-brutal-lime"
                >
                  +
                </span>
              </summary>
              <p className="mt-3 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
                {faq.a}
              </p>
            </details>
          ))}
        </div>

        <div className="bg-brutal-purple p-6 text-white sm:p-8 lg:col-span-4 xl:p-10">
          <h2 className="font-sans text-xl font-black uppercase">OTHER FASTDL DOWNLOADERS</h2>
          <p className="mt-2 font-mono text-xs leading-relaxed text-white/90 sm:text-sm">
            Download public videos from all 4 major platforms with the same 16x accelerated, zero-ad
            engine.
          </p>
          <div className="mt-5 flex flex-col gap-2.5">
            {otherPlatforms.map((p) => (
              <Link
                key={p}
                href={PLATFORM_SEO[p].slug}
                className="flex items-center justify-between border-2 border-black bg-white px-4 py-3 font-mono text-xs font-black uppercase text-black shadow-brutal-sm transition hover:bg-brutal-lime"
              >
                <span>{PLATFORM_SEO[p].name} Video Downloader</span>
                <span aria-hidden="true">→</span>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </article>
  );
}
