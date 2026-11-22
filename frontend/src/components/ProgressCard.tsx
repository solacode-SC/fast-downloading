"use client";

import React from "react";
import type { JobSnapshot } from "@/lib/api";
import { formatBytes, formatEta, formatSpeed } from "@/lib/format";
import { useI18n } from "@/lib/i18n";

interface ProgressCardProps {
  job: JobSnapshot;
  onCancel: () => void;
  onRetry?: () => void;
}

export function ProgressCard({ job, onCancel, onRetry }: ProgressCardProps) {
  const { t } = useI18n();

  const statusText: Record<JobSnapshot["status"], string> = {
    queued: t("statusQueued"),
    resolving: t("analyzing"),
    downloading: t("statusDownloading"),
    merging: t("statusMerging"),
    ready: t("statusReady"),
    failed: t("statusFailed"),
    cancelled: t("statusCancelled"),
  };

  const isActive =
    job.status === "queued" ||
    job.status === "resolving" ||
    job.status === "downloading" ||
    job.status === "merging";

  const pct = Math.max(0, Math.min(100, Math.round(job.progress_percent)));
  const platformNameKey = `platform_${job.platform}_name`;
  const localizedPlatform =
    t(platformNameKey) !== platformNameKey ? t(platformNameKey) : job.platform;

  const localizedErrMsg = job.error
    ? t(`err_${job.error.code}_msg`) !== `err_${job.error.code}_msg`
      ? t(`err_${job.error.code}_msg`)
      : job.error.message
    : "";

  const localizedErrHint = job.error
    ? t(`err_${job.error.code}_hint`) !== `err_${job.error.code}_hint`
      ? t(`err_${job.error.code}_hint`)
      : job.error.hint
    : "";

  return (
    <section
      aria-label="Download progress"
      aria-live="polite"
      className="border-2 border-black bg-brutal-pink p-3 shadow-brutal"
    >
      <div className="border-2 border-black bg-white p-4 dark:bg-[#16161F]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="border-2 border-black bg-brutal-purple px-2 py-0.5 font-mono text-[10px] font-black uppercase text-white">
                {statusText[job.status]}
              </span>
              <span className="font-mono text-[11px] font-bold uppercase text-zinc-600 dark:text-zinc-300">
                {localizedPlatform}
              </span>
            </div>
            <p className="mt-2 truncate font-sans text-base font-black uppercase tracking-tight text-black dark:text-zinc-100">
              {job.filename || job.title || job.url}
            </p>
          </div>

          <span className="border-2 border-black bg-brutal-lime px-3 py-1 font-mono text-sm font-black text-black shadow-brutal-sm">
            {pct}%
          </span>
        </div>

        {/* Brutalist Progress Bar */}
        <div
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          className="mt-4 h-5 w-full overflow-hidden border-2 border-black bg-zinc-100 dark:bg-zinc-800"
        >
          <div
            className={`h-full border-e-2 border-black transition-all duration-300 ${
              job.status === "failed"
                ? "bg-brutal-pink"
                : job.status === "ready"
                  ? "bg-brutal-lime"
                  : "bg-brutal-purple"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>

        {/* Live Telemetry */}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 font-mono text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="border border-black bg-zinc-100 px-2 py-0.5 font-bold text-black">
              {formatBytes(job.downloaded_bytes)}
              {job.total_bytes ? ` / ${formatBytes(job.total_bytes)}` : ""}
            </span>
            {isActive && job.speed_bytes_per_sec && (
              <span className="border border-black bg-brutal-lime px-2 py-0.5 font-bold text-black">
                {t("speed")}: {formatSpeed(job.speed_bytes_per_sec)}
              </span>
            )}
            {isActive && job.eta_seconds != null && (
              <span className="border border-black bg-white px-2 py-0.5 font-bold text-black">
                {t("eta")}: {formatEta(job.eta_seconds)}
              </span>
            )}
          </div>

          {isActive && (
            <button
              type="button"
              onClick={onCancel}
              className="border-2 border-black bg-white px-3 py-1 font-mono text-xs font-black uppercase text-black shadow-brutal-sm transition hover:bg-brutal-pink"
            >
              {t("cancel")} ✕
            </button>
          )}
        </div>

        {/* Error Alert */}
        {job.status === "failed" && job.error && (
          <div
            role="alert"
            className="mt-4 border-2 border-black bg-brutal-pink p-3 font-mono text-xs text-black shadow-brutal-sm"
          >
            <p className="font-black uppercase">
              [{job.error.code}] {localizedErrMsg}
            </p>
            {localizedErrHint && <p className="mt-1 font-medium">{localizedErrHint}</p>}
            {job.error.retryable && onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="mt-2.5 border-2 border-black bg-brutal-lime px-3 py-1.5 font-mono text-xs font-black uppercase text-black shadow-brutal-sm hover:translate-x-[1px] hover:translate-y-[1px]"
              >
                {t("retry")} ↻
              </button>
            )}
          </div>
        )}

        {/* Ready Download Actions */}
        {job.status === "ready" && job.download_url && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <a
              href={job.download_url}
              download={job.filename || undefined}
              className="inline-flex items-center gap-2 border-2 border-black bg-brutal-lime px-5 py-2.5 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal transition hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-brutal-sm"
            >
              <span>
                {t("saveFile")} {job.filesize_bytes ? `(${formatBytes(job.filesize_bytes)})` : ""} ↓
              </span>
            </a>

            {job.subtitle_url && (
              <a
                href={job.subtitle_url}
                download
                className="inline-flex items-center border-2 border-black bg-white px-3.5 py-2 font-mono text-xs font-black uppercase text-black shadow-brutal-sm hover:bg-brutal-pink"
              >
                {t("downloadSubs")} ↓
              </a>
            )}

            {job.thumbnail_url_download && (
              <a
                href={job.thumbnail_url_download}
                download
                className="inline-flex items-center border-2 border-black bg-white px-3.5 py-2 font-mono text-xs font-black uppercase text-black shadow-brutal-sm hover:bg-brutal-pink"
              >
                {t("downloadThumb")} ↓
              </a>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
