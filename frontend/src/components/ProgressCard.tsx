"use client";

import React from "react";
import type { JobSnapshot } from "@/lib/api";
import { formatBytes, formatEta, formatSpeed } from "@/lib/format";
import { useI18n } from "@/lib/i18n";

interface ProgressCardProps {
  job: JobSnapshot;
  onCancel: () => void;
  onRetry?: () => void;
  onNewDownload?: () => void;
}

export function ProgressCard({ job, onCancel, onRetry, onNewDownload }: ProgressCardProps) {
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

  const statusBadgeClass =
    job.status === "failed"
      ? "bg-black text-brutal-pink"
      : job.status === "ready"
        ? "bg-brutal-lime text-black"
        : job.status === "cancelled"
          ? "bg-zinc-200 text-black"
          : "bg-brutal-purple text-white";

  const pctBadgeClass =
    job.status === "failed"
      ? "bg-brutal-pink text-black"
      : job.status === "cancelled"
        ? "bg-zinc-200 text-black"
        : "bg-brutal-lime text-black";

  const hasBytes = job.downloaded_bytes > 0;
  const showTelemetryRow = isActive || hasBytes;

  return (
    <section
      aria-label="Download progress"
      aria-live="polite"
      className="border-2 border-black bg-brutal-pink p-2.5 shadow-brutal sm:p-3"
    >
      <div className="border-2 border-black bg-white p-3.5 sm:p-4 dark:bg-[#16161F]">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`border-2 border-black px-2 py-0.5 font-mono text-[10px] font-black uppercase ${statusBadgeClass}`}
              >
                {statusText[job.status]}
              </span>
              <span className="font-mono text-[11px] font-bold uppercase text-zinc-600 dark:text-zinc-300">
                {localizedPlatform}
              </span>
            </div>
            <p
              dir="auto"
              className="mt-2 truncate font-sans text-sm font-black uppercase tracking-tight text-black sm:text-base dark:text-zinc-100"
            >
              {job.filename || job.title || job.url}
            </p>
          </div>

          <span
            dir="ltr"
            className={`shrink-0 border-2 border-black px-3 py-1 font-mono text-sm font-black shadow-brutal-sm ${pctBadgeClass}`}
          >
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
          {isActive && pct === 0 ? (
            <div className="h-full w-1/4 animate-pulse border-e-2 border-black bg-brutal-purple/75" />
          ) : (
            <div
              className={`h-full transition-all duration-300 ${
                pct > 0 && pct < 100 ? "border-e-2 border-black" : ""
              } ${
                job.status === "failed"
                  ? "bg-brutal-pink"
                  : job.status === "ready"
                    ? "bg-brutal-lime"
                    : "bg-brutal-purple"
              }`}
              style={{ width: `${pct}%` }}
            />
          )}
        </div>

        {/* Live Telemetry (hidden when failed/cancelled at 0 bytes so no empty '—' box renders) */}
        {showTelemetryRow && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 font-mono text-xs">
            <div className="flex flex-wrap items-center gap-2">
              {hasBytes ? (
                <span
                  dir="ltr"
                  className="border border-black bg-zinc-100 px-2 py-0.5 font-bold text-black"
                >
                  {formatBytes(job.downloaded_bytes)}
                  {job.total_bytes ? ` / ${formatBytes(job.total_bytes)}` : ""}
                </span>
              ) : (
                <span className="border border-black bg-zinc-100 px-2 py-0.5 font-bold text-black">
                  {statusText[job.status]}...
                </span>
              )}
              {isActive && job.speed_bytes_per_sec && (
                <span className="border border-black bg-brutal-lime px-2 py-0.5 font-bold text-black">
                  {t("speed")}: <span dir="ltr">{formatSpeed(job.speed_bytes_per_sec)}</span>
                </span>
              )}
              {isActive && job.eta_seconds != null && (
                <span className="border border-black bg-white px-2 py-0.5 font-bold text-black">
                  {t("eta")}: <span dir="ltr">{formatEta(job.eta_seconds)}</span>
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
        )}

        {/* Error Alert */}
        {job.status === "failed" && job.error && (
          <div
            role="alert"
            className="mt-4 border-2 border-black bg-brutal-pink p-3.5 font-mono text-xs text-black shadow-brutal-sm"
          >
            <p className="break-words font-black uppercase leading-snug">
              <span dir="ltr">[{job.error.code}]</span> {localizedErrMsg}
            </p>
            {localizedErrHint && (
              <p className="mt-1 break-words font-medium leading-relaxed">{localizedErrHint}</p>
            )}
            {job.error.retryable && onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="mt-3 inline-flex items-center gap-1.5 border-2 border-black bg-brutal-lime px-3.5 py-1.5 font-mono text-xs font-black uppercase text-black shadow-brutal-sm transition hover:translate-y-[1px] hover:shadow-none"
              >
                <span>{t("retry")}</span>
                <span aria-hidden="true">↻</span>
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
              className="inline-flex items-center gap-2 border-2 border-black bg-brutal-lime px-5 py-2.5 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal transition hover:translate-y-[2px] hover:shadow-brutal-sm ltr:hover:translate-x-[2px] rtl:hover:-translate-x-[2px]"
            >
              <span>{t("saveFile")}</span>
              {job.filesize_bytes ? (
                <span dir="ltr">({formatBytes(job.filesize_bytes)})</span>
              ) : null}
              <span aria-hidden="true">↓</span>
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

            {onNewDownload && (
              <button
                type="button"
                onClick={onNewDownload}
                className="inline-flex items-center gap-1.5 border-2 border-black bg-brutal-purple px-4 py-2.5 font-mono text-xs font-black uppercase tracking-wider text-white shadow-brutal-sm transition hover:bg-[#684de6]"
              >
                <span>{t("downloadAnother")}</span>
                <span aria-hidden="true">+</span>
              </button>
            )}
          </div>
        )}

        {(job.status === "failed" || job.status === "cancelled") && onNewDownload && (
          <div className="mt-3">
            <button
              type="button"
              onClick={onNewDownload}
              className="inline-flex items-center gap-1.5 border-2 border-black bg-white px-3.5 py-1.5 font-mono text-xs font-black uppercase text-black shadow-brutal-sm transition hover:bg-brutal-lime"
            >
              <span>{t("downloadAnother")}</span>
              <span aria-hidden="true">+</span>
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
