"use client";

import React from "react";
import Link from "next/link";
import {
  ApiClientError,
  cancelDownloadJob,
  createDownloadJob,
  fetchJobSnapshot,
  resolveUrl,
  subscribeJobEvents,
  type JobSnapshot,
  type Preset,
  type ResolveResponse,
} from "@/lib/api";
import { formatDuration, formatSpeed } from "@/lib/format";
import { addHistoryItem, clearHistory, loadHistory, type HistoryItem } from "@/lib/history";
import { useI18n } from "@/lib/i18n";
import { detectClientPlatform, extractSharedUrl, PLATFORM_META } from "@/lib/platform";
import { FormatPicker } from "./FormatPicker";
import { HistoryDrawer } from "./HistoryDrawer";
import { ProgressCard } from "./ProgressCard";
import { ToastContainer, type ToastMessage } from "./ToastContainer";

export function DownloaderApp() {
  const { locale, t } = useI18n();
  const [urlInput, setUrlInput] = React.useState("");
  const [resolving, setResolving] = React.useState(false);
  const [quickDownloading, setQuickDownloading] = React.useState(false);
  const [media, setMedia] = React.useState<ResolveResponse | null>(null);
  const [startingJob, setStartingJob] = React.useState(false);
  const [activeJob, setActiveJob] = React.useState<JobSnapshot | null>(null);
  const [history, setHistory] = React.useState<HistoryItem[]>([]);
  const [toasts, setToasts] = React.useState<ToastMessage[]>([]);

  const unsubscribeRef = React.useRef<(() => void) | null>(null);
  const autoDownloadedJobRef = React.useRef<string | null>(null);
  const [lastDownloadOpts, setLastDownloadOpts] = React.useState<{
    preset?: Preset;
    formatId?: string | null;
    subtitleLang?: string | null;
    downloadThumbnail: boolean;
    playlistItem?: number | null;
  } | null>(null);

  const pushToast = React.useCallback(
    (title: string, hint?: string, variant: "error" | "info" = "error") => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev.slice(-3), { id, title, hint, variant }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((item) => item.id !== id));
      }, 8000);
    },
    []
  );

  const pushApiError = React.useCallback(
    (err: unknown) => {
      if (err instanceof ApiClientError) {
        const msgKey = `err_${err.detail.code}_msg`;
        const hintKey = `err_${err.detail.code}_hint`;
        const msg = t(msgKey) !== msgKey ? t(msgKey) : err.detail.message;
        const hint = t(hintKey) !== hintKey ? t(hintKey) : err.detail.hint;
        pushToast(msg, hint, "error");
      } else {
        pushToast(t("err_NETWORK_msg"), t("err_NETWORK_hint"), "error");
      }
    },
    [pushToast, t]
  );

  const dismissToast = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const attachJobStream = React.useCallback(
    (jobId: string, resolvedMedia: ResolveResponse) => {
      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeJobEvents(
        jobId,
        (snap) => {
          setActiveJob(snap);
          if (snap.status === "ready" && snap.download_url) {
            setHistory(
              addHistoryItem({
                id: snap.job_id,
                url: resolvedMedia.normalized_url,
                platform: snap.platform,
                title: snap.title || resolvedMedia.title,
                thumbnailUrl: snap.thumbnail_url || resolvedMedia.thumbnail_url,
                filename: snap.filename,
                filesizeBytes: snap.filesize_bytes,
                createdAt: Date.now(),
              })
            );
            if (autoDownloadedJobRef.current !== snap.job_id) {
              autoDownloadedJobRef.current = snap.job_id;
              const anchor = document.createElement("a");
              anchor.href = snap.download_url;
              if (snap.filename) anchor.download = snap.filename;
              anchor.rel = "noopener";
              document.body.appendChild(anchor);
              anchor.click();
              anchor.remove();
            }
          }
        },
        () => {
          void fetchJobSnapshot(jobId)
            .then((snap) => setActiveJob(snap))
            .catch(() => pushToast(t("err_NETWORK_msg"), t("err_NETWORK_hint"), "error"));
        }
      );
    },
    [pushToast, t]
  );

  const handleResolve = React.useCallback(
    async (targetUrl?: string): Promise<ResolveResponse | null> => {
      const candidate = (targetUrl ?? urlInput).trim();
      if (!candidate) return null;
      setResolving(true);
      setMedia(null);
      try {
        const result = await resolveUrl(candidate);
        setMedia(result);
        return result;
      } catch (err) {
        pushApiError(err);
        return null;
      } finally {
        setResolving(false);
      }
    },
    [urlInput, pushApiError]
  );

  const startJobForMedia = React.useCallback(
    async (
      targetMedia: ResolveResponse,
      opts: {
        preset?: Preset;
        formatId?: string | null;
        subtitleLang?: string | null;
        downloadThumbnail: boolean;
        playlistItem?: number | null;
      }
    ) => {
      setLastDownloadOpts(opts);
      setStartingJob(true);
      try {
        const created = await createDownloadJob({
          url: targetMedia.normalized_url,
          preset: opts.preset,
          format_id: opts.formatId ?? null,
          subtitle_lang: opts.subtitleLang ?? null,
          download_thumbnail: opts.downloadThumbnail,
          playlist_item: opts.playlistItem ?? null,
        });
        const initialSnap = await fetchJobSnapshot(created.job_id);
        setActiveJob(initialSnap);
        attachJobStream(created.job_id, targetMedia);
      } catch (err) {
        pushApiError(err);
      } finally {
        setStartingJob(false);
      }
    },
    [attachJobStream, pushApiError]
  );

  const handleQuickDownload = async () => {
    const candidate = urlInput.trim();
    if (!candidate) return;
    setQuickDownloading(true);
    try {
      const resolved =
        media && (media.url === candidate || media.normalized_url === candidate)
          ? media
          : await handleResolve(candidate);
      if (resolved) {
        await startJobForMedia(resolved, {
          preset: "best",
          formatId: null,
          subtitleLang: null,
          downloadThumbnail: false,
          playlistItem: resolved.entries.length > 0 ? 1 : null,
        });
      }
    } finally {
      setQuickDownloading(false);
    }
  };

  React.useEffect(() => {
    const savedHistory = loadHistory();
    const params = new URLSearchParams(window.location.search);
    const shared = extractSharedUrl(params);
    queueMicrotask(() => {
      setHistory(savedHistory);
      if (shared) {
        setUrlInput(shared);
        void handleResolve(shared);
      }
    });
    return () => {
      unsubscribeRef.current?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrlInput(text.trim());
        void handleResolve(text.trim());
      }
    } catch {
      pushToast(t("paste"), "Ctrl+V / Cmd+V", "info");
    }
  };

  const handleStartDownload = async (opts: {
    preset?: Preset;
    formatId?: string | null;
    subtitleLang?: string | null;
    downloadThumbnail: boolean;
    playlistItem?: number | null;
  }) => {
    if (!media) return;
    await startJobForMedia(media, opts);
  };

  const handleCancelJob = async () => {
    if (!activeJob) return;
    unsubscribeRef.current?.();
    try {
      await cancelDownloadJob(activeJob.job_id);
      setActiveJob((prev) => (prev ? { ...prev, status: "cancelled" } : null));
    } catch (err) {
      pushApiError(err);
    }
  };

  const detectedPlatform = detectClientPlatform(urlInput);
  const currentPlatKey = media?.platform ?? detectedPlatform;
  const localizedPlatName = currentPlatKey
    ? t(`platform_${currentPlatKey}_name`)
    : t("codeAutoDetect");

  return (
    <div className="flex min-h-[calc(100vh-56px)] w-full flex-col">
      {/* =================================================================
          1. FULL-SCREEN HERO SPLIT BENTO GRID
         ================================================================= */}
      <section
        aria-label="Video downloader hero"
        className="grid w-full grid-cols-1 border-b-2 border-black lg:min-h-[54vh] lg:grid-cols-12"
      >
        {/* Left Hero Column */}
        <div className="bg-grid-paper flex flex-col justify-between border-b-2 border-black p-5 sm:p-8 md:p-10 lg:col-span-7 lg:border-b-0 lg:border-e-2 xl:p-14">
          <div className="space-y-5 xl:space-y-6">
            <div className="inline-flex items-center gap-2 border-2 border-black bg-brutal-purple px-3 py-1 font-mono text-[11px] font-black uppercase tracking-wider text-white shadow-brutal-sm sm:text-xs">
              <span>{t("heroPill")}</span>
            </div>

            <h1 className="font-sans text-3xl font-black uppercase leading-[1.02] tracking-tight text-black sm:text-5xl md:text-6xl xl:text-7xl dark:text-zinc-50">
              {t("heroTitleLine1")}
              <br />
              {t("heroTitleLine2")}
            </h1>

            <p className="max-w-2xl font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm md:text-base dark:text-zinc-300">
              {t("subtitle")} {t("heroTechSub")}
            </p>

            {/* Full-Width Responsive URL Input Form */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void handleResolve();
              }}
              className="max-w-3xl space-y-3.5 pt-1"
            >
              <label htmlFor="video-url-input" className="sr-only">
                Video URL
              </label>
              <div className="flex flex-col border-2 border-black bg-white shadow-brutal sm:flex-row sm:items-stretch dark:bg-zinc-900">
                <div className="flex flex-1 items-stretch">
                  {detectedPlatform && (
                    <span
                      className={`flex shrink-0 items-center border-e-2 border-black px-3 font-mono text-xs font-black uppercase ${PLATFORM_META[detectedPlatform].badgeClass}`}
                    >
                      {PLATFORM_META[detectedPlatform].code}
                    </span>
                  )}
                  <input
                    id="video-url-input"
                    type="url"
                    dir="ltr"
                    inputMode="url"
                    autoComplete="off"
                    spellCheck={false}
                    required
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    placeholder={t("urlPlaceholder")}
                    className="min-w-0 flex-1 bg-transparent px-3.5 py-3.5 text-left font-mono text-xs font-bold text-black placeholder:text-zinc-400 focus:outline-none sm:py-4 sm:text-sm dark:text-zinc-100"
                  />
                </div>
                {urlInput ? (
                  <button
                    type="button"
                    onClick={() => {
                      setUrlInput("");
                      setMedia(null);
                    }}
                    className="border-t-2 border-black bg-zinc-100 px-4 py-2.5 font-mono text-xs font-black uppercase text-black hover:bg-brutal-pink sm:border-t-0 sm:border-s-2"
                  >
                    {t("clear")}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => void handlePaste()}
                    className="border-t-2 border-black bg-brutal-pink px-5 py-2.5 font-mono text-xs font-black uppercase text-black transition hover:bg-brutal-lime sm:border-t-0 sm:border-s-2"
                  >
                    {t("paste")}
                  </button>
                )}
              </div>

              {/* Dual Hero Buttons */}
              <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:flex-wrap sm:items-center">
                <button
                  type="submit"
                  disabled={resolving || quickDownloading || !urlInput.trim()}
                  className="inline-flex w-full items-center justify-center gap-2 border-2 border-black bg-brutal-lime px-6 py-3.5 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal transition hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-brutal-sm disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:text-sm"
                >
                  <span>{resolving ? t("analyzing") : t("analyzeFormatsBtn")}</span>
                </button>

                <button
                  type="button"
                  disabled={resolving || quickDownloading || !urlInput.trim()}
                  onClick={() => void handleQuickDownload()}
                  className="inline-flex w-full items-center justify-center gap-2 border-2 border-black bg-white px-6 py-3.5 font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal transition hover:translate-x-[2px] hover:translate-y-[2px] hover:bg-brutal-pink hover:shadow-brutal-sm disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:text-sm"
                >
                  <span>{quickDownloading ? t("starting") : t("quickDownloadBtn")}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Bottom-left Platform Icon Boxes */}
          <div className="mt-8 space-y-2.5">
            <p className="font-mono text-[10px] font-black uppercase tracking-widest text-zinc-600 sm:text-xs dark:text-zinc-400">
              {t("supportedPlatformsLabel")}
            </p>
            <div className="flex flex-wrap items-center gap-2.5">
              {(["youtube", "x", "instagram", "facebook"] as const).map((p) => {
                const active = detectedPlatform === p;
                return (
                  <div
                    key={p}
                    title={t(`platform_${p}_name`)}
                    className={`flex h-10 px-3 items-center justify-center border-2 border-black font-mono text-xs font-black shadow-brutal-sm transition sm:h-11 ${
                      active ? "bg-brutal-lime text-black" : "bg-white text-black"
                    }`}
                  >
                    {t(`platform_${p}_name`)}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Hero Column */}
        <div className="relative flex min-h-[340px] flex-col items-center justify-center bg-brutal-pink p-6 sm:p-10 lg:col-span-5 xl:p-14">
          <div className="relative w-full max-w-sm xl:max-w-md">
            <div
              aria-hidden="true"
              className="translate-x-2.5 -translate-y-2.5 border-2 border-black bg-brutal-lime p-4 sm:translate-x-3.5 sm:-translate-y-3.5"
            >
              <div className="h-48 w-full sm:h-56" />
            </div>

            <div className="absolute inset-0 flex flex-col justify-between overflow-hidden border-2 border-black bg-zinc-900 p-4 text-white shadow-brutal">
              {media?.thumbnail_url ? (
                <>
                  <img
                    src={media.thumbnail_url}
                    alt={media.title}
                    className="h-full w-full object-cover"
                  />
                  <div className="absolute top-2.5 start-2.5 border-2 border-black bg-brutal-lime px-2.5 py-0.5 font-mono text-[10px] font-black uppercase text-black">
                    {t(`platform_${media.platform}_name`)}
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between border-b border-zinc-700 pb-2 font-mono text-[10px] text-zinc-400 sm:text-xs">
                    <span>{t("previewStreamCopy")}</span>
                    <span className="bg-brutal-lime px-1.5 py-0.5 font-black text-black">
                      {t("previewReady")}
                    </span>
                  </div>
                  <div className="my-auto space-y-2.5 py-4 text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center border-2 border-white bg-brutal-purple font-mono text-xl font-black text-white">
                      ↓
                    </div>
                    <p className="font-sans text-xs font-black uppercase tracking-wider text-zinc-200 sm:text-sm">
                      {t("previewIdleText")}
                    </p>
                  </div>
                  <div className="flex items-center justify-between font-mono text-[10px] text-brutal-lime sm:text-xs">
                    <span>{t("previewCodecsLeft")}</span>
                    <span>{t("previewCodecsRight")}</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Overlapping Electric Purple Telemetry Card */}
          <div className="relative z-10 -mt-6 ms-auto w-full max-w-xs border-2 border-black bg-brutal-purple p-4 font-mono text-[11px] leading-relaxed text-white shadow-brutal sm:max-w-sm sm:text-xs">
            <p className="font-bold text-brutal-lime">&gt; {t("codeConst")} &#123;</p>
            <p className="ps-3">
              {t("codePlatform")}:{" "}
              <span className="text-brutal-lime">&apos;{localizedPlatName}&apos;</span>,
            </p>
            <p className="ps-3">
              {t("codeFormats")}:{" "}
              <span className="text-brutal-lime">
                &apos;
                {media
                  ? `${media.formats.length} ${t("codeStreamsUnit")}`
                  : t("codeDefaultFormats")}
                &apos;
              </span>
              ,
            </p>
            <p className="ps-3">
              {t("codeRemux")}:{" "}
              <span className="text-brutal-lime">&apos;{t("codeDefaultRemux")}&apos;</span>,
            </p>
            <p className="ps-3">
              {t("codeSpeed")}:{" "}
              <span className="text-brutal-lime">
                &apos;
                {activeJob?.speed_bytes_per_sec
                  ? formatSpeed(activeJob.speed_bytes_per_sec)
                  : t("codeDefaultSpeed")}
                &apos;
              </span>
            </p>
            <p className="font-bold text-brutal-lime">&#125;</p>
          </div>
        </div>
      </section>

      {/* =================================================================
          2. FULL-WIDTH HORIZONTAL PLATFORMS STRIP
         ================================================================= */}
      <section
        id="platforms-strip"
        aria-label="Supported platforms"
        className="grid w-full grid-cols-1 border-b-2 border-black bg-white sm:grid-cols-12 dark:bg-[#16161F]"
      >
        <div className="flex flex-row items-center justify-between border-b-2 border-black bg-brutal-purple px-5 py-4 font-sans text-sm font-black uppercase tracking-wider text-white sm:col-span-3 sm:flex-col sm:items-start sm:justify-center sm:border-b-0 sm:border-e-2 lg:col-span-2 lg:px-8">
          <span>{t("platformsTitle")}</span>
          <span aria-hidden="true" className="text-lg sm:mt-1">
            {locale === "ar" ? "←" : "→"}
          </span>
        </div>

        <div className="grid grid-cols-2 divide-black sm:col-span-9 sm:grid-cols-4 sm:divide-x-2 lg:col-span-10">
          {(["youtube", "x", "instagram", "facebook"] as const).map((p) => {
            const meta = PLATFORM_META[p];
            return (
              <div
                key={p}
                className="flex flex-col items-center justify-center gap-1.5 border-b border-e border-black p-4 text-center sm:border-b-0 sm:border-e-0 lg:py-6"
              >
                <span className="flex h-10 w-10 items-center justify-center border-2 border-black bg-black font-mono text-xs font-black text-white shadow-brutal-sm">
                  {meta.code}
                </span>
                <span className="font-mono text-xs font-black uppercase text-black sm:text-sm dark:text-zinc-100">
                  {t(`platform_${p}_name`)}
                </span>
                <span className="font-mono text-[10px] text-zinc-600 sm:text-xs dark:text-zinc-400">
                  {t(`platform_${p}_spec`)}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* =================================================================
          3. FULL-WIDTH MAIN BENTO WORKSPACE
         ================================================================= */}
      <section
        id="workspace-section"
        aria-label="Downloader workspace and history"
        className="grid w-full flex-1 grid-cols-1 border-b-2 border-black lg:grid-cols-12"
      >
        {/* Left Main Workspace */}
        <div className="space-y-6 border-b-2 border-black bg-white p-5 sm:p-8 lg:col-span-8 lg:border-b-0 lg:border-e-2 xl:p-12 dark:bg-[#12121A]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-sans text-lg font-black uppercase tracking-tight text-black sm:text-xl dark:text-zinc-100">
              {t("inspectorTitle")}
            </h2>
            <div className="flex items-center gap-1.5">
              <span className="flex h-8 w-8 items-center justify-center border-2 border-black bg-brutal-pink font-mono text-xs font-black text-black shadow-brutal-sm">
                &lt;
              </span>
              <span className="flex h-8 w-8 items-center justify-center border-2 border-black bg-brutal-pink font-mono text-xs font-black text-black shadow-brutal-sm">
                &gt;
              </span>
            </div>
          </div>

          {activeJob && (
            <ProgressCard
              job={activeJob}
              onCancel={() => void handleCancelJob()}
              onRetry={
                lastDownloadOpts ? () => void handleStartDownload(lastDownloadOpts) : undefined
              }
            />
          )}

          {media ? (
            <div className="border-2 border-black bg-white shadow-brutal dark:bg-[#16161F]">
              <div className="border-b-2 border-black bg-brutal-pink p-3 sm:p-5">
                <div className="flex flex-col gap-4 border-2 border-black bg-white p-4 sm:flex-row dark:bg-zinc-900">
                  {media.thumbnail_url && (
                    <img
                      src={media.thumbnail_url}
                      alt={media.title}
                      className="aspect-video w-full shrink-0 border-2 border-black object-cover bg-zinc-200 sm:w-56 md:w-64"
                    />
                  )}
                  <div className="min-w-0 flex-1 space-y-2.5">
                    <div className="flex flex-wrap items-center gap-2 font-mono text-[11px] font-black uppercase">
                      <span className={`px-2 py-0.5 ${PLATFORM_META[media.platform].badgeClass}`}>
                        {t(`platform_${media.platform}_name`)}
                      </span>
                      {media.duration_seconds != null && (
                        <span className="border-2 border-black bg-brutal-lime px-2 py-0.5 text-black">
                          {formatDuration(media.duration_seconds)}
                        </span>
                      )}
                      {media.cached && (
                        <span className="border-2 border-black bg-brutal-purple px-2 py-0.5 text-white">
                          {t("cachedBadge")}
                        </span>
                      )}
                      <span className="border border-black bg-zinc-100 px-2 py-0.5 text-black">
                        {media.resolve_ms}ms
                      </span>
                    </div>

                    <h3 className="line-clamp-2 font-sans text-lg font-black uppercase leading-snug text-black sm:text-xl dark:text-zinc-50">
                      {media.title}
                    </h3>

                    {media.uploader && (
                      <p className="font-mono text-xs font-bold text-zinc-700 dark:text-zinc-300">
                        @{media.uploader}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="p-4 sm:p-6 xl:p-8">
                <FormatPicker
                  media={media}
                  busy={startingJob}
                  onStartDownload={(opts) => void handleStartDownload(opts)}
                />
              </div>
            </div>
          ) : (
            <div className="border-2 border-black bg-white shadow-brutal dark:bg-[#16161F]">
              <div className="border-b-2 border-black bg-brutal-pink p-4 sm:p-6">
                <div className="bg-grid-paper flex flex-col items-center justify-center border-2 border-black px-5 py-10 text-center sm:py-14">
                  <span className="border-2 border-black bg-brutal-lime px-3 py-1 font-mono text-xs font-black uppercase text-black shadow-brutal-sm">
                    {t("readyForExtractionBadge")}
                  </span>
                  <p className="mt-4 font-sans text-2xl font-black uppercase tracking-tight text-black sm:text-3xl dark:text-zinc-100">
                    {t("readyForExtractionFormats")}
                  </p>
                  <p className="mt-2 max-w-lg font-mono text-xs leading-relaxed text-zinc-600 sm:text-sm dark:text-zinc-400">
                    {t("readyForExtractionDesc")}
                  </p>
                </div>
              </div>
              <div className="space-y-3 p-5 sm:p-6">
                <h3 className="font-sans text-base font-black uppercase text-black dark:text-zinc-100">
                  {t("zeroTranscodingTitle")}
                </h3>
                <div className="flex flex-wrap gap-2 font-mono text-xs font-bold">
                  <span className="border-2 border-black bg-white px-2.5 py-1 text-black">
                    {t("tagYtdlp")}
                  </span>
                  <span className="border-2 border-black bg-white px-2.5 py-1 text-black">
                    {t("tagCurlCffi")}
                  </span>
                  <span className="border-2 border-black bg-white px-2.5 py-1 text-black">
                    {t("tagFfmpegCopy")}
                  </span>
                  <span className="border-2 border-black bg-white px-2.5 py-1 text-black">
                    {t("tagHttpRange")}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Acid Lime Column */}
        <div className="bg-brutal-lime p-5 sm:p-8 lg:col-span-4 xl:p-10">
          <HistoryDrawer
            items={history}
            onSelectUrl={(u) => {
              setUrlInput(u);
              void handleResolve(u);
            }}
            onClear={() => {
              clearHistory();
              setHistory([]);
            }}
          />
        </div>
      </section>

      {/* =================================================================
          4. FULL-WIDTH BOTTOM SPLIT BENTO
         ================================================================= */}
      <section
        id="pipeline-section"
        aria-label="Extraction pipeline and privacy guarantee"
        className="grid w-full grid-cols-1 border-b-2 border-black lg:grid-cols-12"
      >
        <div className="flex flex-row items-center justify-between border-b-2 border-black bg-brutal-pink px-5 py-4 lg:col-span-2 lg:flex-col lg:items-start lg:justify-end lg:border-b-0 lg:border-e-2 lg:p-8">
          <span className="font-sans text-base font-black uppercase tracking-wider text-black">
            {t("pipelineTitle")}
          </span>
          <span aria-hidden="true" className="text-xl font-black text-black lg:mt-1">
            {locale === "ar" ? "←" : "→"}
          </span>
        </div>

        <div className="border-b-2 border-black bg-white p-6 sm:p-8 lg:col-span-6 lg:border-b-0 lg:border-e-2 xl:p-12 dark:bg-[#16161F]">
          <div className="relative space-y-6 border-s-2 border-black ps-6 dark:border-zinc-500">
            <div className="relative">
              <span className="absolute -start-[31px] top-1 h-3.5 w-3.5 border-2 border-black bg-brutal-lime" />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-sans text-sm font-black uppercase text-black sm:text-base dark:text-zinc-100">
                  {t("pipe1Title")}
                </h3>
                <span className="font-mono text-xs font-bold text-zinc-500">{t("pipe1Time")}</span>
              </div>
              <p className="mt-1 font-mono text-xs text-zinc-600 sm:text-sm dark:text-zinc-400">
                {t("pipe1Desc")}
              </p>
            </div>

            <div className="relative">
              <span className="absolute -start-[31px] top-1 h-3.5 w-3.5 border-2 border-black bg-brutal-pink" />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-sans text-sm font-black uppercase text-black sm:text-base dark:text-zinc-100">
                  {t("pipe2Title")}
                </h3>
                <span className="font-mono text-xs font-bold text-zinc-500">{t("pipe2Time")}</span>
              </div>
              <p className="mt-1 font-mono text-xs text-zinc-600 sm:text-sm dark:text-zinc-400">
                {t("pipe2Desc")}
              </p>
            </div>

            <div className="relative">
              <span className="absolute -start-[31px] top-1 h-3.5 w-3.5 border-2 border-black bg-brutal-purple" />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-sans text-sm font-black uppercase text-black sm:text-base dark:text-zinc-100">
                  {t("pipe3Title")}
                </h3>
                <span className="font-mono text-xs font-bold text-zinc-500">{t("pipe3Time")}</span>
              </div>
              <p className="mt-1 font-mono text-xs text-zinc-600 sm:text-sm dark:text-zinc-400">
                {t("pipe3Desc")}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-grid-purple relative flex flex-col justify-between overflow-hidden p-6 sm:p-8 lg:col-span-4 xl:p-12">
          <div className="space-y-3">
            <h2 className="font-sans text-2xl font-black uppercase leading-tight text-white sm:text-3xl">
              {t("privacyLine1")}
              <br />
              {t("privacyLine2")}
              <br />
              {t("privacyLine3")}
              <br />
              {t("privacyLine4")}
            </h2>
            <p className="font-mono text-xs text-white/90 sm:text-sm">{t("privacyDesc")}</p>
          </div>

          <div className="mt-6">
            <Link
              href="/legal"
              className="inline-flex items-center gap-2 border-2 border-black bg-white px-5 py-3 font-mono text-xs font-black uppercase text-black shadow-brutal transition hover:bg-brutal-lime"
            >
              <span>{t("readLegalBtn")}</span>
            </Link>
          </div>
        </div>
      </section>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
