"use client";

import React, { useState } from "react";
import type { FormatItem, Preset, ResolveResponse } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/format";
import { useI18n } from "@/lib/i18n";

interface FormatPickerProps {
  media: ResolveResponse;
  busy: boolean;
  onStartDownload: (opts: {
    preset?: Preset;
    formatId?: string | null;
    subtitleLang?: string | null;
    downloadThumbnail: boolean;
    playlistItem?: number | null;
  }) => void;
}

export function FormatPicker({ media, busy, onStartDownload }: FormatPickerProps) {
  const { t } = useI18n();
  const [selectedPreset, setSelectedPreset] = useState<Preset>("best");
  const [selectedFormatId, setSelectedFormatId] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [subtitleLang, setSubtitleLang] = useState<string>("");
  const [downloadThumb, setDownloadThumb] = useState(false);
  const [playlistItem, setPlaylistItem] = useState<number>(1);

  const handleDownload = () => {
    onStartDownload({
      preset: selectedFormatId ? undefined : selectedPreset,
      formatId: selectedFormatId,
      subtitleLang: subtitleLang || null,
      downloadThumbnail: downloadThumb,
      playlistItem: media.entries.length > 0 ? playlistItem : null,
    });
  };

  const getPresetLabel = (id: Preset, fallback: string) => {
    const key = `preset_${id}_label`;
    const val = t(key);
    return val !== key ? val : fallback;
  };

  const getPresetDesc = (id: Preset, fallback: string) => {
    const key = `preset_${id}_desc`;
    const val = t(key);
    return val !== key ? val : fallback;
  };

  const activePresetLabel = getPresetLabel(selectedPreset, selectedPreset.toUpperCase());

  return (
    <div className="space-y-5">
      {/* Multi-item selector for Instagram carousels & YouTube playlists */}
      {media.entries.length > 0 && (
        <div className="space-y-2">
          <label
            htmlFor="entry-select"
            className="block font-mono text-xs font-black uppercase tracking-wider text-black dark:text-zinc-100"
          >
            {t("playlistItems")} ({media.entries.length})
          </label>
          <select
            id="entry-select"
            value={playlistItem}
            onChange={(e) => setPlaylistItem(Number(e.target.value))}
            className="w-full border-2 border-black bg-white px-3 py-2.5 font-mono text-xs font-bold text-black shadow-brutal-sm focus:outline-none dark:bg-zinc-900 dark:text-zinc-100"
          >
            {media.entries.map((entry) => (
              <option key={entry.id} value={entry.index}>
                #{entry.index} — {entry.title}
                {entry.duration_seconds ? ` (${formatDuration(entry.duration_seconds)})` : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Presets Header */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-mono text-xs font-black uppercase tracking-wider text-black sm:text-sm dark:text-zinc-100">
            {t("presetsTitle")}
          </h3>
          {media.formats.length > 0 && (
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              aria-expanded={showAdvanced}
              className="border-2 border-black bg-brutal-pink px-3 py-1 font-mono text-[11px] font-black uppercase text-black shadow-brutal-sm transition hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none"
            >
              {showAdvanced
                ? `${t("hideAdvanced")} ↑`
                : `${t("advancedFormats")} (${media.formats.length}) ↓`}
            </button>
          )}
        </div>

        {/* Responsive Brutalist Preset Cards */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {media.presets
            .filter((p) => p.available)
            .map((preset) => {
              const active = !selectedFormatId && selectedPreset === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => {
                    setSelectedFormatId(null);
                    setSelectedPreset(preset.id);
                  }}
                  aria-pressed={active}
                  className={`flex flex-col items-start border-2 border-black p-3.5 text-start transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black ${
                    active
                      ? "translate-x-[2px] translate-y-[2px] bg-brutal-lime text-black shadow-brutal-sm"
                      : "bg-white text-black shadow-brutal hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
                  }`}
                >
                  <div className="flex w-full items-center justify-between gap-2">
                    <span className="font-sans text-sm font-black uppercase tracking-tight">
                      {getPresetLabel(preset.id, preset.label)}
                    </span>
                    <span
                      className={`border-2 border-black px-1.5 py-0.5 font-mono text-[10px] font-black uppercase ${
                        active ? "bg-white text-black" : "bg-brutal-purple text-white"
                      }`}
                    >
                      {preset.estimated_ext}
                    </span>
                  </div>
                  <span
                    className={`mt-1 font-mono text-[11px] leading-snug ${
                      active ? "text-black/85" : "text-zinc-600 dark:text-zinc-400"
                    }`}
                  >
                    {getPresetDesc(preset.id, preset.description)}
                  </span>
                  <div className="mt-2.5 flex items-center gap-2 font-mono text-[11px] font-bold">
                    {preset.estimated_height && (
                      <span className="border border-black bg-white px-1.5 py-0.5 text-black">
                        {preset.estimated_height}P
                      </span>
                    )}
                    {preset.estimated_size_bytes && (
                      <span className="border border-black bg-white px-1.5 py-0.5 text-black">
                        ~{formatBytes(preset.estimated_size_bytes)}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
        </div>
      </div>

      {/* Collapsible Advanced Formats Table */}
      {showAdvanced && media.formats.length > 0 && (
        <div className="overflow-x-auto border-2 border-black bg-white shadow-brutal dark:bg-zinc-900">
          <table className="w-full min-w-[520px] text-start font-mono text-xs">
            <thead className="border-b-2 border-black bg-brutal-purple text-white">
              <tr>
                <th className="px-3 py-2 text-start font-black uppercase">{t("tableId")}</th>
                <th className="px-3 py-2 text-start font-black uppercase">{t("tableQuality")}</th>
                <th className="px-3 py-2 text-start font-black uppercase">{t("tableCodec")}</th>
                <th className="px-3 py-2 text-start font-black uppercase">{t("tableBitrate")}</th>
                <th className="px-3 py-2 text-start font-black uppercase">{t("tableSize")}</th>
                <th className="px-3 py-2 text-end font-black uppercase">{t("tablePick")}</th>
              </tr>
            </thead>
            <tbody className="divide-y-2 divide-black">
              {media.formats.map((f: FormatItem) => {
                const isSelected = selectedFormatId === f.format_id;
                return (
                  <tr
                    key={f.format_id}
                    className={
                      isSelected
                        ? "bg-brutal-lime text-black"
                        : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
                    }
                  >
                    <td className="px-3 py-2 font-bold">{f.format_id}</td>
                    <td className="px-3 py-2">
                      <span className="font-black uppercase">{f.resolution || f.ext}</span>
                      {f.fps ? ` ${Math.round(f.fps)}fps` : ""}
                      {f.is_hdr && (
                        <span className="ms-1.5 border border-black bg-brutal-pink px-1 py-0.5 text-[10px] font-black text-black">
                          {t("hdrBadge")}
                        </span>
                      )}
                      <span className="ms-1.5 text-[10px] opacity-75">
                        {f.is_audio_only
                          ? t("audioOnly")
                          : f.is_video_only
                            ? t("videoOnly")
                            : t("progressive")}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-[11px]">
                      {[f.ext, f.vcodec, f.acodec].filter(Boolean).join(" / ")}
                    </td>
                    <td className="px-3 py-2">
                      {f.tbr_kbps
                        ? `${Math.round(f.tbr_kbps)}k`
                        : f.abr_kbps
                          ? `${Math.round(f.abr_kbps)}k`
                          : "—"}
                    </td>
                    <td className="px-3 py-2">
                      {formatBytes(f.filesize_bytes ?? f.filesize_approx_bytes)}
                    </td>
                    <td className="px-3 py-2 text-end">
                      <button
                        type="button"
                        onClick={() => setSelectedFormatId(f.format_id)}
                        className={`border-2 border-black px-2.5 py-1 font-mono text-[11px] font-black uppercase shadow-brutal-sm transition ${
                          isSelected
                            ? "bg-black text-brutal-lime"
                            : "bg-white text-black hover:bg-brutal-lime"
                        }`}
                      >
                        {isSelected ? t("selectedBtn") : t("selectBtn")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Extras: optional subtitles & thumbnail */}
      <div className="flex flex-wrap items-center gap-4 border-2 border-black bg-zinc-50 p-3.5 font-mono text-xs dark:bg-zinc-900">
        {media.subtitles.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="sub-select" className="font-bold uppercase">
              {t("subtitlesOpt")}:
            </label>
            <select
              id="sub-select"
              value={subtitleLang}
              onChange={(e) => setSubtitleLang(e.target.value)}
              className="border-2 border-black bg-white px-2 py-1 font-mono text-xs font-bold text-black dark:bg-zinc-800 dark:text-zinc-100"
            >
              <option value="">{t("noSubtitles")}</option>
              {media.subtitles.map((s) => (
                <option key={`${s.lang}-${s.auto ? "a" : "m"}`} value={s.lang}>
                  {s.name} ({s.lang}){s.auto ? ` [${t("autoSubTag")}]` : ""}
                </option>
              ))}
            </select>
          </div>
        )}

        <label className="flex cursor-pointer items-center gap-2 font-bold uppercase">
          <input
            type="checkbox"
            checked={downloadThumb}
            onChange={(e) => setDownloadThumb(e.target.checked)}
            className="h-4 w-4 border-2 border-black accent-black"
          />
          <span>{t("thumbnailOpt")}</span>
        </label>
      </div>

      {/* Primary Brutalist Download CTA */}
      <button
        type="button"
        disabled={busy}
        onClick={handleDownload}
        className="flex w-full items-center justify-center gap-2 border-2 border-black bg-brutal-lime px-6 py-4 font-mono text-sm font-black uppercase tracking-wider text-black shadow-brutal transition hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-brutal-sm disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span>
          {busy
            ? t("starting")
            : selectedFormatId
              ? `${t("downloadNow")} (#${selectedFormatId}) ↓`
              : `${t("downloadNow")} (${activePresetLabel}) ↓`}
        </span>
      </button>
    </div>
  );
}
