"use client";

import React from "react";
import { formatBytes } from "@/lib/format";
import type { HistoryItem } from "@/lib/history";
import { useI18n } from "@/lib/i18n";
import { PLATFORM_META } from "@/lib/platform";

interface HistoryDrawerProps {
  items: HistoryItem[];
  onSelectUrl: (url: string) => void;
  onClear: () => void;
}

export function HistoryDrawer({ items, onSelectUrl, onClear }: HistoryDrawerProps) {
  const { locale, t } = useI18n();

  return (
    <section
      aria-label="Download history"
      className="flex h-full flex-col justify-between space-y-4"
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-sans text-sm font-black uppercase tracking-tight text-black sm:text-base">
            {t("historyTitle")}
          </h2>
          <span
            dir="ltr"
            className="shrink-0 border-2 border-black bg-white px-2 py-0.5 font-mono text-[11px] font-black text-black"
          >
            {items.length}
          </span>
        </div>

        {items.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3].map((slot) => (
              <div
                key={slot}
                className="flex min-h-[92px] flex-col items-center justify-center border-2 border-black bg-white/85 p-4 text-center shadow-brutal"
              >
                <span className="font-sans text-xs font-black uppercase text-black/80 sm:text-sm">
                  {t("slotLabel")} 0{slot} · {t("emptySlot")}
                </span>
                <span className="mt-1 font-mono text-[11px] leading-snug text-black/65">
                  {t("emptyHistory")}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <ul className="space-y-3">
            {items.slice(0, 6).map((item) => {
              const meta = PLATFORM_META[item.platform];
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onSelectUrl(item.url)}
                    className="flex w-full items-center gap-3 border-2 border-black bg-white p-3 text-start text-black shadow-brutal transition hover:translate-y-[2px] hover:bg-zinc-50 hover:shadow-brutal-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black ltr:hover:translate-x-[2px] rtl:hover:-translate-x-[2px]"
                  >
                    {item.thumbnailUrl ? (
                      <img
                        src={item.thumbnailUrl}
                        alt=""
                        className="h-12 w-16 shrink-0 border-2 border-black bg-zinc-200 object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div
                        dir="ltr"
                        className="flex h-12 w-16 shrink-0 items-center justify-center border-2 border-black bg-brutal-pink font-mono text-xs font-black"
                      >
                        {meta.code}
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p dir="auto" className="truncate font-sans text-xs font-black uppercase">
                        {item.title}
                      </p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2 font-mono text-[10px] font-bold">
                        <span className={`px-1.5 py-0.5 ${meta.badgeClass}`}>
                          {t(`platform_${item.platform}_name`)}
                        </span>
                        {item.filesizeBytes && (
                          <span
                            dir="ltr"
                            className="border border-black bg-zinc-100 px-1.5 py-0.5 text-black"
                          >
                            {formatBytes(item.filesizeBytes)}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <button
        type="button"
        disabled={items.length === 0}
        onClick={onClear}
        className="mt-4 flex w-full items-center justify-between border-2 border-black bg-white px-4 py-3 font-mono text-xs font-black uppercase text-black shadow-brutal transition hover:translate-y-[2px] hover:bg-brutal-pink hover:shadow-brutal-sm disabled:cursor-not-allowed disabled:opacity-50 ltr:hover:translate-x-[2px] rtl:hover:-translate-x-[2px]"
      >
        <span>{t("clearHistory")}</span>
        <span aria-hidden="true">{locale === "ar" ? "←" : "→"}</span>
      </button>
    </section>
  );
}
