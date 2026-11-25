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
  type Platform,
  type Preset,
  type ResolveResponse,
} from "@/lib/api";
import { formatDuration, formatSpeed } from "@/lib/format";
import { addHistoryItem, clearHistory, loadHistory, type HistoryItem } from "@/lib/history";
import { useI18n } from "@/lib/i18n";
import { detectClientPlatform, extractSharedUrl, PLATFORM_META } from "@/lib/platform";
import { trackUmamiEvent } from "@/lib/umami";
import { FormatPicker } from "./FormatPicker";
import { HistoryDrawer } from "./HistoryDrawer";
import { ProgressCard } from "./ProgressCard";
import { ToastContainer, type ToastMessage } from "./ToastContainer";

const PLATFORM_ROUTES: Record<Platform, string> = {
  youtube: "/youtube-downloader",
  x: "/twitter-video-downloader",
  instagram: "/instagram-downloader",
  facebook: "/facebook-downloader",
};

const TERMINAL_JOB_STATUSES = new Set<JobSnapshot["status"]>(["ready", "failed", "cancelled"]);

function extractCleanUrl(raw: string): string {
  const trimmed = raw.trim();
  const match = trimmed.match(/https?:\/\/[^\s"'<>]+/i);
  return match ? match[0] : trimmed;
}

function triggerBrowserFileDownload(downloadUrl: string, filename?: string | null): void {
  const anchor = document.createElement("a");
  anchor.href = downloadUrl;
  if (filename) anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

export interface DownloaderAppProps {
  initialPlatform?: Platform;
  heroOverride?: {
    pill?: string;
    titleLine1?: string;
    titleLine2?: string;
    subtitle?: string;
    techSub?: string;
    placeholder?: string;
  };
  hideHomeFaq?: boolean;
}

export function DownloaderApp({
  initialPlatform,
  heroOverride,
  hideHomeFaq = false,
}: DownloaderAppProps = {}) {
  const { locale, t } = useI18n();
  const [urlInput, setUrlInput] = React.useState("");
  const [resolving, setResolving] = React.useState(false);
  const [quickDownloading, setQuickDownloading] = React.useState(false);
  const [media, setMedia] = React.useState<ResolveResponse | null>(null);
  const [startingJob, setStartingJob] = React.useState(false);
  const [activeJob, setActiveJob] = React.useState<JobSnapshot | null>(null);
  const [history, setHistory] = React.useState<HistoryItem[]>([]);
  const [toasts, setToasts] = React.useState<ToastMessage[]>([]);

  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const unsubscribeRef = React.useRef<(() => void) | null>(null);
  const resolveAbortRef = React.useRef<AbortController | null>(null);
  const resolveReqIdRef = React.useRef(0);
  const inFlightResolveRef = React.useRef<{
    url: string;
    promise: Promise<ResolveResponse | null>;
  } | null>(null);
  const downloadRunIdRef = React.useRef(0);
  const autoDownloadedRunRef = React.useRef<number | null>(null);

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
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
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

  const handleReadySnapshot = React.useCallback(
    (snap: JobSnapshot, resolvedMedia: ResolveResponse, runId: number) => {
      if (snap.status !== "ready" || !snap.download_url) return;
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
      if (autoDownloadedRunRef.current !== runId) {
        autoDownloadedRunRef.current = runId;
        trackUmamiEvent("download_ready", { platform: snap.platform });
        triggerBrowserFileDownload(snap.download_url, snap.filename);
      }
    },
    []
  );

  const attachJobStream = React.useCallback(
    (jobId: string, resolvedMedia: ResolveResponse, runId: number) => {
      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeJobEvents(
        jobId,
        (snap) => {
          if (downloadRunIdRef.current !== runId) return;
          setActiveJob(snap);
          if (snap.status === "ready" && snap.download_url) {
            handleReadySnapshot(snap, resolvedMedia, runId);
          }
        },
        () => {
          if (downloadRunIdRef.current !== runId) return;
          void fetchJobSnapshot(jobId)
            .then((snap) => {
              if (downloadRunIdRef.current !== runId) return;
              setActiveJob(snap);
              if (snap.status === "ready" && snap.download_url) {
                handleReadySnapshot(snap, resolvedMedia, runId);
              }
            })
            .catch(() => pushToast(t("err_NETWORK_msg"), t("err_NETWORK_hint"), "error"));
        }
      );
    },
    [handleReadySnapshot, pushToast, t]
  );

  const clearTerminalJobIfAny = React.useCallback(() => {
    setActiveJob((prev) => {
      if (!prev || TERMINAL_JOB_STATUSES.has(prev.status)) {
        unsubscribeRef.current?.();
        unsubscribeRef.current = null;
        return null;
      }
      return prev;
    });
  }, []);

  const resetForNewDownload = React.useCallback((focusInput = true) => {
    resolveAbortRef.current?.abort();
    resolveAbortRef.current = null;
    inFlightResolveRef.current = null;
    resolveReqIdRef.current += 1;
    downloadRunIdRef.current += 1;
    autoDownloadedRunRef.current = null;
    unsubscribeRef.current?.();
    unsubscribeRef.current = null;
    setResolving(false);
    setStartingJob(false);
    setQuickDownloading(false);
    setUrlInput("");
    setMedia(null);
    setActiveJob(null);
    setLastDownloadOpts(null);
    if (focusInput) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, []);

  const handleResolve = React.useCallback(
    async (targetUrl?: string): Promise<ResolveResponse | null> => {
      const candidate = extractCleanUrl(targetUrl ?? urlInput);
      if (!candidate) return null;

      // Abort any previous in-flight resolve so stale responses never overwrite the new link
      resolveAbortRef.current?.abort();
      const controller = new AbortController();
      resolveAbortRef.current = controller;
      const reqId = ++resolveReqIdRef.current;

      setResolving(true);
      setMedia(null);
      setLastDownloadOpts(null);
      clearTerminalJobIfAny();

      const promise = (async (): Promise<ResolveResponse | null> => {
        try {
          const result = await resolveUrl(candidate, controller.signal);
          if (reqId !== resolveReqIdRef.current) return null;
          setMedia(result);
          trackUmamiEvent("resolve_success", { platform: result.platform });
          return result;
        } catch (err) {
          if (reqId !== resolveReqIdRef.current) return null;
          pushApiError(err);
          return null;
        } finally {
          if (reqId === resolveReqIdRef.current) {
            setResolving(false);
            if (inFlightResolveRef.current?.url === candidate) {
              inFlightResolveRef.current = null;
            }
          }
        }
      })();

      inFlightResolveRef.current = { url: candidate, promise };
      return promise;
    },
    [urlInput, pushApiError, clearTerminalJobIfAny]
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
      const runId = ++downloadRunIdRef.current;
      autoDownloadedRunRef.current = null;
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;

      setLastDownloadOpts(opts);
      setStartingJob(true);
      setActiveJob({
        job_id: `pending-${runId}`,
        platform: targetMedia.platform,
        url: targetMedia.normalized_url,
        title: targetMedia.title,
        thumbnail_url: targetMedia.thumbnail_url,
        status: "queued",
        progress_percent: 0,
        downloaded_bytes: 0,
        total_bytes: null,
        speed_bytes_per_sec: null,
        eta_seconds: null,
        phase_detail: "Starting download...",
        download_token: null,
        download_url: null,
        filename: null,
        mime_type: null,
        filesize_bytes: null,
        subtitle_token: null,
        subtitle_url: null,
        thumbnail_token: null,
        thumbnail_url_download: null,
        error: null,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
        expires_at: null,
      });

      try {
        trackUmamiEvent("download_started", {
          platform: targetMedia.platform,
          preset: opts.preset ?? opts.formatId ?? "custom",
        });
        const created = await createDownloadJob({
          url: targetMedia.normalized_url,
          preset: opts.preset,
          format_id: opts.formatId ?? null,
          subtitle_lang: opts.subtitleLang ?? null,
          download_thumbnail: opts.downloadThumbnail,
          playlist_item: opts.playlistItem ?? null,
        });
        if (downloadRunIdRef.current !== runId) return;

        const initialSnap = await fetchJobSnapshot(created.job_id);
        if (downloadRunIdRef.current !== runId) return;

        setActiveJob(initialSnap);
        if (initialSnap.status === "ready" && initialSnap.download_url) {
          handleReadySnapshot(initialSnap, targetMedia, runId);
        } else if (!TERMINAL_JOB_STATUSES.has(initialSnap.status)) {
          attachJobStream(created.job_id, targetMedia, runId);
        }
      } catch (err) {
        if (downloadRunIdRef.current === runId) {
          setActiveJob(null);
          pushApiError(err);
        }
      } finally {
        if (downloadRunIdRef.current === runId) {
          setStartingJob(false);
        }
      }
    },
    [attachJobStream, handleReadySnapshot, pushApiError]
  );

  const handleQuickDownload = async () => {
    const candidate = extractCleanUrl(urlInput);
    if (!candidate) return;
    if (candidate !== urlInput) {
      setUrlInput(candidate);
    }
    setQuickDownloading(true);
    try {
      let resolved: ResolveResponse | null = null;
      if (media && (media.url === candidate || media.normalized_url === candidate)) {
        resolved = media;
      } else if (inFlightResolveRef.current && inFlightResolveRef.current.url === candidate) {
        // Reuse the in-flight resolve triggered by paste instead of duplicating or blocking
        resolved = await inFlightResolveRef.current.promise;
      } else {
        resolved = await handleResolve(candidate);
      }

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
      resolveAbortRef.current?.abort();
      unsubscribeRef.current?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyPastedText = React.useCallback(
    (rawText: string) => {
      const cleaned = extractCleanUrl(rawText);
      if (!cleaned) return;
      // Clear any previous completed/failed job and stale media immediately so pasting a 2nd link always works cleanly
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;
      setActiveJob(null);
      setMedia(null);
      setLastDownloadOpts(null);
      autoDownloadedRunRef.current = null;
      setUrlInput(cleaned);
      void handleResolve(cleaned);
    },
    [handleResolve]
  );

  const handlePasteButton = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text && text.trim()) {
        applyPastedText(text);
      }
    } catch {
      inputRef.current?.focus();
      inputRef.current?.select();
      pushToast(t("paste"), "Ctrl+V / Cmd+V", "info");
    }
  };

  const handleInputPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData("text");
    if (!pasted || !pasted.trim()) return;
    // Always replace existing URL instead of concatenating onto the previous video link
    e.preventDefault();
    applyPastedText(pasted);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextVal = e.target.value;
    setUrlInput(nextVal);
    const trimmed = nextVal.trim();
    // Immediately invalidate stale media & finished job when the URL changes so the user never downloads the previous video
    if (media && trimmed !== media.url && trimmed !== media.normalized_url) {
      setMedia(null);
      setLastDownloadOpts(null);
      clearTerminalJobIfAny();
    } else if (!trimmed) {
      setMedia(null);
      setLastDownloadOpts(null);
      clearTerminalJobIfAny();
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
    unsubscribeRef.current = null;
    if (activeJob.job_id.startsWith("pending-")) {
      downloadRunIdRef.current += 1;
      setActiveJob(null);
      setStartingJob(false);
      return;
    }
    try {
      await cancelDownloadJob(activeJob.job_id);
      setActiveJob((prev) => (prev ? { ...prev, status: "cancelled" } : null));
    } catch (err) {
      pushApiError(err);
    }
  };

  const detectedPlatform = detectClientPlatform(urlInput);
  const currentPlatKey = media?.platform ?? detectedPlatform ?? initialPlatform ?? null;
  const localizedPlatName = currentPlatKey
    ? t(`platform_${currentPlatKey}_name`)
    : t("codeAutoDetect");

  const formatsSummary = media
    ? `${media.formats.length} ${t("codeStreamsUnit")}`
    : t("codeDefaultFormats");
  const speedSummary = activeJob?.speed_bytes_per_sec
    ? formatSpeed(activeJob.speed_bytes_per_sec)
    : t("codeDefaultSpeed");

  const heroPillText = heroOverride?.pill ?? t("heroPill");
  const heroLine1 = heroOverride?.titleLine1 ?? t("heroTitleLine1");
  const heroLine2 = heroOverride?.titleLine2 ?? t("heroTitleLine2");
  const heroSubtitleText = heroOverride?.subtitle ?? t("subtitle");
  const heroTechSubText = heroOverride?.techSub ?? t("heroTechSub");
  const heroPlaceholder = heroOverride?.placeholder ?? t("urlPlaceholder");

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
        <div className="bg-grid-paper flex flex-col justify-between border-b-2 border-black p-4 sm:p-8 md:p-10 lg:col-span-7 lg:border-b-0 lg:border-e-2 xl:p-14">
          <div className="space-y-4 sm:space-y-5 xl:space-y-6">
            <div className="inline-flex max-w-full items-center gap-2 border-2 border-black bg-brutal-purple px-3 py-1 font-mono text-[11px] font-black uppercase leading-snug tracking-wider text-white shadow-brutal-sm sm:text-xs">
              <span className="break-words">{heroPillText}</span>
            </div>

            <h1
              className={`break-words font-sans text-3xl font-black uppercase tracking-tight text-black sm:text-4xl md:text-5xl 2xl:text-6xl dark:text-zinc-50 ${
                locale === "ar" ? "leading-[1.32]" : "leading-[1.06]"
              }`}
            >
              {heroLine1}
              <br />
              {heroLine2}
            </h1>

            <p className="max-w-2xl font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm md:text-base dark:text-zinc-300">
              {heroSubtitleText} {heroTechSubText}
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
                <div className="flex min-w-0 flex-1 items-stretch">
                  {detectedPlatform && (
                    <span
                      dir="ltr"
                      className={`flex shrink-0 items-center border-e-2 border-black px-3 font-mono text-xs font-black uppercase ${PLATFORM_META[detectedPlatform].badgeClass}`}
                    >
                      {PLATFORM_META[detectedPlatform].code}
                    </span>
                  )}
                  <input
                    ref={inputRef}
                    id="video-url-input"
                    type="url"
                    dir="ltr"
                    inputMode="url"
                    autoComplete="off"
                    spellCheck={false}
                    required
                    value={urlInput}
                    onChange={handleInputChange}
                    onPaste={handleInputPaste}
                    onFocus={(e) => {
                      if (e.currentTarget.value) {
                        e.currentTarget.select();
                      }
                    }}
                    placeholder={heroPlaceholder}
                    className="min-w-0 flex-1 bg-transparent px-3.5 py-3.5 text-left font-mono text-xs font-bold text-black placeholder:text-zinc-400 focus:outline-none sm:py-4 sm:text-sm dark:text-zinc-100"
                  />
                </div>
                <div className="flex shrink-0 items-stretch border-t-2 border-black sm:border-s-2 sm:border-t-0">
                  <button
                    type="button"
                    onClick={() => void handlePasteButton()}
                    className="flex-1 bg-brutal-pink px-4 py-2.5 font-mono text-xs font-black uppercase text-black transition hover:bg-brutal-lime sm:flex-none sm:px-5"
                  >
                    {t("paste")}
                  </button>
                  {urlInput && (
                    <button
                      type="button"
                      onClick={() => resetForNewDownload(true)}
                      className="flex-1 border-s-2 border-black bg-zinc-100 px-4 py-2.5 font-mono text-xs font-black uppercase text-black transition hover:bg-brutal-pink sm:flex-none"
                    >
                      {t("clear")}
                    </button>
                  )}
                </div>
              </div>

              {/* Balanced 2-Column Hero CTA Buttons */}
              <div className="grid grid-cols-1 gap-3 pt-1 sm:grid-cols-2">
                <button
                  type="submit"
                  disabled={resolving || quickDownloading || !urlInput.trim()}
                  className="inline-flex min-h-[48px] w-full items-center justify-center gap-2 border-2 border-black bg-brutal-lime px-4 py-3 text-center font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal transition hover:translate-y-[2px] hover:shadow-brutal-sm disabled:cursor-not-allowed disabled:opacity-50 sm:px-5 sm:text-sm ltr:hover:translate-x-[2px] rtl:hover:-translate-x-[2px]"
                >
                  <span>{resolving ? t("analyzing") : t("analyzeFormatsBtn")}</span>
                </button>

                <button
                  type="button"
                  disabled={quickDownloading || startingJob || !urlInput.trim()}
                  onClick={() => void handleQuickDownload()}
                  className="inline-flex min-h-[48px] w-full items-center justify-center gap-2 border-2 border-black bg-white px-4 py-3 text-center font-mono text-xs font-black uppercase tracking-wider text-black shadow-brutal transition hover:translate-y-[2px] hover:bg-brutal-pink hover:shadow-brutal-sm disabled:cursor-not-allowed disabled:opacity-50 sm:px-5 sm:text-sm ltr:hover:translate-x-[2px] rtl:hover:-translate-x-[2px]"
                >
                  <span>
                    {quickDownloading || startingJob ? t("starting") : t("quickDownloadBtn")}
                  </span>
                </button>
              </div>
            </form>
          </div>

          {/* Bottom-left Platform Badges (Internal SEO Links) */}
          <div className="mt-7 space-y-2.5 sm:mt-8">
            <p className="font-mono text-[11px] font-black uppercase tracking-widest text-zinc-600 sm:text-xs dark:text-zinc-400">
              {t("supportedPlatformsLabel")}
            </p>
            <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center sm:gap-2.5">
              {(["youtube", "x", "instagram", "facebook"] as const).map((p) => {
                const active = (detectedPlatform ?? initialPlatform) === p;
                return (
                  <Link
                    key={p}
                    href={PLATFORM_ROUTES[p]}
                    title={`${t(`platform_${p}_name`)} Video Downloader`}
                    className={`flex h-10 items-center justify-center gap-1.5 border-2 border-black px-3 font-mono text-xs font-black shadow-brutal-sm transition sm:h-11 ${
                      active ? "bg-brutal-lime text-black" : "bg-white text-black hover:bg-zinc-50"
                    }`}
                  >
                    <span
                      dir="ltr"
                      className="border border-black bg-black px-1.5 py-0.5 text-[10px] text-white"
                    >
                      {PLATFORM_META[p].code}
                    </span>
                    <span>{t(`platform_${p}_name`)}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Hero Column */}
        <div className="relative flex min-h-[340px] flex-col items-center justify-center bg-brutal-pink p-5 sm:p-10 lg:col-span-5 xl:p-12">
          <div className="relative w-full max-w-sm xl:max-w-md">
            <div
              aria-hidden="true"
              className="-translate-y-2 border-2 border-black bg-brutal-lime p-4 sm:-translate-y-3 ltr:translate-x-2 sm:ltr:translate-x-3 rtl:-translate-x-2 sm:rtl:-translate-x-3"
            >
              <div className="h-44 w-full sm:h-52" />
            </div>

            <div className="absolute inset-0 flex flex-col justify-between overflow-hidden border-2 border-black bg-zinc-900 p-4 text-white shadow-brutal">
              {media?.thumbnail_url ? (
                <>
                  <img
                    src={media.thumbnail_url}
                    alt={media.title}
                    className="h-full w-full object-cover"
                  />
                  <div className="absolute start-2.5 top-2.5 border-2 border-black bg-brutal-lime px-2.5 py-0.5 font-mono text-[10px] font-black uppercase text-black">
                    {t(`platform_${media.platform}_name`)}
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between gap-2 border-b border-zinc-700 pb-2 font-mono text-[10px] text-zinc-400 sm:text-xs">
                    <span className="truncate">{t("previewStreamCopy")}</span>
                    <span className="shrink-0 bg-brutal-lime px-1.5 py-0.5 font-black text-black">
                      {t("previewReady")}
                    </span>
                  </div>
                  <div className="my-auto space-y-2.5 py-3 text-center">
                    <div className="mx-auto flex h-11 w-11 items-center justify-center border-2 border-white bg-brutal-purple font-mono text-lg font-black text-white sm:h-12 sm:w-12 sm:text-xl">
                      ↓
                    </div>
                    <p className="px-2 font-sans text-xs font-black uppercase leading-snug tracking-wider text-zinc-200 sm:text-sm">
                      {t("previewIdleText")}
                    </p>
                  </div>
                  <div
                    dir="ltr"
                    className="flex items-center justify-between font-mono text-[10px] text-brutal-lime sm:text-xs"
                  >
                    <span>{t("previewCodecsLeft")}</span>
                    <span>{t("previewCodecsRight")}</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Structured Multi-Language Safe Live Telemetry Card */}
          <div className="relative z-10 -mt-5 w-full max-w-sm border-2 border-black bg-brutal-purple text-white shadow-brutal sm:ms-auto sm:max-w-sm">
            <div
              dir="ltr"
              className="flex items-center justify-between border-b-2 border-black bg-black px-3 py-1.5 font-mono text-[10px] font-black uppercase text-brutal-lime"
            >
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 bg-brutal-pink" />
                <span className="inline-block h-2 w-2 bg-brutal-lime" />
                <span>FASTDL // TELEMETRY</span>
              </span>
              <span>v1.1</span>
            </div>
            <dl className="divide-y divide-white/20 px-3.5 py-2 font-mono text-[11px] sm:text-xs">
              <div className="flex items-center justify-between gap-3 py-1.5">
                <dt className="font-bold uppercase text-white/85">{t("codePlatform")}</dt>
                <dd className="border border-black bg-brutal-lime px-2 py-0.5 font-black text-black">
                  {localizedPlatName}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3 py-1.5">
                <dt className="font-bold uppercase text-white/85">{t("codeFormats")}</dt>
                <dd dir="auto" className="truncate font-bold text-brutal-lime">
                  {formatsSummary}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3 py-1.5">
                <dt className="font-bold uppercase text-white/85">{t("codeRemux")}</dt>
                <dd dir="auto" className="truncate font-bold text-brutal-lime">
                  {t("codeDefaultRemux")}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3 py-1.5">
                <dt className="font-bold uppercase text-white/85">{t("codeSpeed")}</dt>
                <dd dir="auto" className="truncate font-bold text-brutal-lime">
                  {speedSummary}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      {/* =================================================================
          2. FULL-WIDTH HORIZONTAL PLATFORMS STRIP (Internal SEO Links)
         ================================================================= */}
      <section
        id="platforms-strip"
        aria-label="Supported platforms"
        className="grid w-full grid-cols-1 border-b-2 border-black bg-white sm:grid-cols-12 dark:bg-[#16161F]"
      >
        <div className="flex flex-row items-center justify-between border-b-2 border-black bg-brutal-purple px-5 py-3.5 font-sans text-sm font-black uppercase tracking-wider text-white sm:col-span-3 sm:flex-col sm:items-start sm:justify-center sm:border-b-0 sm:border-e-2 lg:col-span-2 lg:px-8">
          <span>{t("platformsTitle")}</span>
          <span aria-hidden="true" className="text-lg sm:mt-1">
            {locale === "ar" ? "←" : "→"}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:col-span-9 sm:grid-cols-4 lg:col-span-10">
          {(["youtube", "x", "instagram", "facebook"] as const).map((p, idx) => {
            const meta = PLATFORM_META[p];
            return (
              <Link
                key={p}
                href={PLATFORM_ROUTES[p]}
                className={`flex flex-col items-center justify-center gap-1.5 border-black p-4 text-center transition hover:bg-brutal-lime/25 lg:py-6 ${
                  idx < 2 ? "border-b-2 sm:border-b-0" : ""
                } ${idx % 2 === 0 ? "border-e-2 sm:border-e-0" : ""} ${
                  idx > 0 ? "sm:border-s-2" : ""
                }`}
              >
                <span
                  dir="ltr"
                  className="flex h-10 w-10 items-center justify-center border-2 border-black bg-black font-mono text-xs font-black text-white shadow-brutal-sm"
                >
                  {meta.code}
                </span>
                <span className="font-mono text-xs font-black uppercase text-black sm:text-sm dark:text-zinc-100">
                  {t(`platform_${p}_name`)}
                </span>
                <span className="font-mono text-[11px] text-zinc-600 sm:text-xs dark:text-zinc-400">
                  {t(`platform_${p}_spec`)}
                </span>
              </Link>
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
        <div className="space-y-6 border-b-2 border-black bg-white p-4 sm:p-8 lg:col-span-8 lg:border-b-0 lg:border-e-2 xl:p-12 dark:bg-[#12121A]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-sans text-lg font-black uppercase tracking-tight text-black sm:text-xl dark:text-zinc-100">
              {t("inspectorTitle")}
            </h2>
            <div dir="ltr" className="flex items-center gap-1.5">
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
              onNewDownload={() => resetForNewDownload(true)}
            />
          )}

          {media ? (
            <div className="border-2 border-black bg-white shadow-brutal dark:bg-[#16161F]">
              <div className="border-b-2 border-black bg-brutal-pink p-3 sm:p-5">
                <div className="flex flex-col gap-4 border-2 border-black bg-white p-3.5 sm:flex-row sm:p-4 dark:bg-zinc-900">
                  {media.thumbnail_url && (
                    <img
                      src={media.thumbnail_url}
                      alt={media.title}
                      className="aspect-video w-full shrink-0 border-2 border-black bg-zinc-200 object-cover sm:w-52 md:w-64"
                    />
                  )}
                  <div className="min-w-0 flex-1 space-y-2.5">
                    <div className="flex flex-wrap items-center gap-2 font-mono text-[11px] font-black uppercase">
                      <span className={`px-2 py-0.5 ${PLATFORM_META[media.platform].badgeClass}`}>
                        {t(`platform_${media.platform}_name`)}
                      </span>
                      {media.duration_seconds != null && (
                        <span
                          dir="ltr"
                          className="border-2 border-black bg-brutal-lime px-2 py-0.5 text-black"
                        >
                          {formatDuration(media.duration_seconds)}
                        </span>
                      )}
                      {media.cached && (
                        <span className="border-2 border-black bg-brutal-purple px-2 py-0.5 text-white">
                          {t("cachedBadge")}
                        </span>
                      )}
                      <span
                        dir="ltr"
                        className="border border-black bg-zinc-100 px-2 py-0.5 text-black"
                      >
                        {media.resolve_ms}ms
                      </span>
                    </div>

                    <h3
                      dir="auto"
                      className="line-clamp-2 break-words font-sans text-base font-black uppercase leading-snug text-black sm:text-xl dark:text-zinc-50"
                    >
                      {media.title}
                    </h3>

                    {media.uploader && (
                      <p
                        dir="auto"
                        className="truncate font-mono text-xs font-bold text-zinc-700 dark:text-zinc-300"
                      >
                        @{media.uploader}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="p-4 sm:p-6 xl:p-8">
                <FormatPicker
                  key={media.normalized_url}
                  media={media}
                  busy={startingJob}
                  onStartDownload={(opts) => void handleStartDownload(opts)}
                />
              </div>
            </div>
          ) : (
            <div className="border-2 border-black bg-white shadow-brutal dark:bg-[#16161F]">
              <div className="border-b-2 border-black bg-brutal-pink p-3.5 sm:p-6">
                <div className="bg-grid-paper flex flex-col items-center justify-center border-2 border-black px-4 py-9 text-center sm:px-6 sm:py-14">
                  <span className="border-2 border-black bg-brutal-lime px-3 py-1 font-mono text-xs font-black uppercase text-black shadow-brutal-sm">
                    {t("readyForExtractionBadge")}
                  </span>
                  <p
                    dir="ltr"
                    className="mt-4 font-sans text-xl font-black uppercase tracking-tight text-black sm:text-3xl dark:text-zinc-100"
                  >
                    {t("readyForExtractionFormats")}
                  </p>
                  <p className="mt-2.5 max-w-lg font-mono text-xs leading-relaxed text-zinc-600 sm:text-sm dark:text-zinc-400">
                    {t("readyForExtractionDesc")}
                  </p>
                </div>
              </div>
              <div className="space-y-3 p-4 sm:p-6">
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
        <div className="bg-brutal-lime p-4 sm:p-8 lg:col-span-4 xl:p-10">
          <HistoryDrawer
            items={history}
            onSelectUrl={(u) => {
              applyPastedText(u);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
            onClear={() => {
              clearHistory();
              setHistory([]);
            }}
          />
        </div>
      </section>

      {/* =================================================================
          4. FULL-WIDTH BOTTOM SPLIT BENTO (RTL-Safe Numbered Steps)
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

        <div className="border-b-2 border-black bg-white p-5 sm:p-8 lg:col-span-6 lg:border-b-0 lg:border-e-2 xl:p-12 dark:bg-[#16161F]">
          <div className="space-y-4">
            {[
              {
                num: "01",
                badgeBg: "bg-brutal-lime text-black",
                title: t("pipe1Title"),
                time: t("pipe1Time"),
                desc: t("pipe1Desc"),
              },
              {
                num: "02",
                badgeBg: "bg-brutal-pink text-black",
                title: t("pipe2Title"),
                time: t("pipe2Time"),
                desc: t("pipe2Desc"),
              },
              {
                num: "03",
                badgeBg: "bg-brutal-purple text-white",
                title: t("pipe3Title"),
                time: t("pipe3Time"),
                desc: t("pipe3Desc"),
              },
            ].map((step) => (
              <div
                key={step.num}
                className="flex items-start gap-3.5 border-2 border-black bg-zinc-50 p-3.5 shadow-brutal-sm sm:p-4 dark:bg-zinc-900"
              >
                <span
                  dir="ltr"
                  className={`flex h-8 w-8 shrink-0 items-center justify-center border-2 border-black font-mono text-xs font-black ${step.badgeBg}`}
                >
                  {step.num}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="font-sans text-sm font-black uppercase text-black sm:text-base dark:text-zinc-100">
                      {step.title}
                    </h3>
                    <span className="border border-black bg-white px-2 py-0.5 font-mono text-[11px] font-bold text-black">
                      {step.time}
                    </span>
                  </div>
                  <p className="mt-1.5 font-mono text-xs leading-relaxed text-zinc-600 sm:text-sm dark:text-zinc-400">
                    {step.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-grid-purple relative flex flex-col justify-between overflow-hidden p-6 sm:p-8 lg:col-span-4 xl:p-12">
          <div className="space-y-3">
            <h2
              className={`font-sans text-2xl font-black uppercase text-white sm:text-3xl ${
                locale === "ar" ? "leading-relaxed" : "leading-tight"
              }`}
            >
              {t("privacyLine1")}
              <br />
              {t("privacyLine2")}
              <br />
              {t("privacyLine3")}
              <br />
              {t("privacyLine4")}
            </h2>
            <p className="font-mono text-xs leading-relaxed text-white/90 sm:text-sm">
              {t("privacyDesc")}
            </p>
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

      {/* =================================================================
          5. SEO & GEO KNOWLEDGE + FAQ SECTION (Home Page)
         ================================================================= */}
      {!hideHomeFaq && (
        <section
          id="faq-section"
          aria-label="Frequently asked questions and supported features"
          className="grid w-full grid-cols-1 border-b-2 border-black bg-white lg:grid-cols-12 dark:bg-[#12121A]"
        >
          <div className="border-b-2 border-black bg-brutal-lime p-5 sm:p-8 lg:col-span-4 lg:border-b-0 lg:border-e-2 xl:p-12">
            <span className="inline-block border-2 border-black bg-black px-2.5 py-1 font-mono text-[11px] font-black uppercase text-brutal-lime">
              {t("faqBadge")}
            </span>
            <h2 className="mt-4 font-sans text-2xl font-black uppercase leading-tight text-black sm:text-3xl">
              {t("faqSectionTitle")}
            </h2>
            <p className="mt-3 font-mono text-xs leading-relaxed text-black/85 sm:text-sm">
              {t("faqSectionDesc")}
            </p>
            <div className="mt-6 space-y-2">
              <p className="font-mono text-[11px] font-black uppercase tracking-wider text-black">
                {t("dedicatedToolsLabel")}
              </p>
              <div className="flex flex-wrap gap-2">
                {(["youtube", "x", "instagram", "facebook"] as const).map((p) => (
                  <Link
                    key={p}
                    href={PLATFORM_ROUTES[p]}
                    className="border-2 border-black bg-white px-3 py-1.5 font-mono text-xs font-black uppercase text-black shadow-brutal-sm transition hover:bg-brutal-pink"
                  >
                    {t(`platform_${p}_name`)} →
                  </Link>
                ))}
              </div>
            </div>
          </div>

          <div className="divide-y-2 divide-black lg:col-span-8">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <details
                key={n}
                open={n <= 2}
                className="group bg-white p-5 transition open:bg-zinc-50 sm:p-6 dark:bg-[#16161F] dark:open:bg-zinc-900"
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-sans text-sm font-black uppercase text-black sm:text-base dark:text-zinc-100">
                  <span>{t(`faq${n}Q`)}</span>
                  <span
                    aria-hidden="true"
                    className="flex h-7 w-7 shrink-0 items-center justify-center border-2 border-black bg-brutal-pink font-mono text-xs font-black text-black transition group-open:rotate-45 group-open:bg-brutal-lime"
                  >
                    +
                  </span>
                </summary>
                <p className="mt-3 font-mono text-xs leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
                  {t(`faq${n}A`)}
                </p>
              </details>
            ))}
          </div>
        </section>
      )}

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
