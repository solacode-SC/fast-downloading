"""Core media extractor built on yt-dlp Python API with layered Anti-Block (L1-L7) & speed tuning."""

from __future__ import annotations

import asyncio
import logging
import shutil
import socket
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp
import yt_dlp.extractor.youtube.pot.utils as _yt_pot_utils

from app.config import Settings
from app.errors import AppError, ErrorCode, classify_ytdlp_error, is_auth_failure, is_proxy_failure
from app.metrics import EXTRACTION_FAILURES
from app.schemas import Platform, Preset, ResolveResponse
from app.security.sanitize import sanitize_filename
from app.services.circuit_breaker import CircuitBreaker, backoff_sleep, jitter_sleep
from app.services.cookies import CookieManager
from app.services.formats import (
    build_presets,
    build_ytdlp_format_options,
    parse_entries,
    parse_formats,
    parse_subtitles,
)
from app.services.fxtwitter import download_fxtwitter_video, fetch_fxtwitter_info
from app.services.platforms import ALLOWED_YTDLP_EXTRACTORS
from app.services.proxies import ProxyEntry, ProxyPool

logger = logging.getLogger(__name__)


class DownloadCancelledError(Exception):
    """Raised inside yt-dlp progress hook when a job is cancelled by the user."""


@dataclass
class AttemptPlan:
    player_client: str | None
    proxy: ProxyEntry | None
    use_cookies: bool
    use_impersonate: bool
    skip_webpage: bool = False


@dataclass
class DownloadArtifact:
    media_path: Path
    filename: str
    ext: str
    title: str
    filesize_bytes: int
    subtitle_path: Path | None = None
    thumbnail_path: Path | None = None


def _resolve_impersonate_target(target_name: str) -> Any | None:
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget

        return ImpersonateTarget.from_str(target_name)
    except Exception:
        return None


def is_curl_cffi_available() -> bool:
    try:
        import curl_cffi  # noqa: F401

        return True
    except ImportError:
        return False


def is_aria2c_available() -> bool:
    return shutil.which("aria2c") is not None


def _enable_extended_pot_clients() -> None:
    """
    Allow bgutil-ytdlp-pot-provider to mint PLAYER and GVS PO tokens for mobile/VR
    InnerTube clients (ANDROID_VR, ANDROID, IOS, VISIONOS) in addition to WEBPO_CLIENTS.
    Must run before yt-dlp lazily imports yt_dlp_plugins.extractor.getpot_bgutil.
    """
    extended = tuple(dict.fromkeys((*_yt_pot_utils.WEBPO_CLIENTS, "ANDROID_VR", "ANDROID", "IOS", "VISIONOS")))
    if set(_yt_pot_utils.WEBPO_CLIENTS) >= {"ANDROID_VR", "ANDROID", "IOS", "VISIONOS"}:
        return

    orig_binding = _yt_pot_utils.get_webpo_content_binding

    def _patched_content_binding(
        request: Any,
        webpo_clients: Any = extended,
        bind_to_visitor_id: bool = False,
    ) -> Any:
        return orig_binding(request, webpo_clients=extended, bind_to_visitor_id=bind_to_visitor_id)

    _yt_pot_utils.WEBPO_CLIENTS = extended
    _yt_pot_utils.get_webpo_content_binding = _patched_content_binding

    bgutil_mod: Any = sys.modules.get("yt_dlp_plugins.extractor.getpot_bgutil")
    if bgutil_mod is not None and hasattr(bgutil_mod, "BgUtilPTPBase"):
        bgutil_mod.BgUtilPTPBase._SUPPORTED_CLIENTS = extended

    bgutil_http_mod: Any = sys.modules.get("yt_dlp_plugins.extractor.getpot_bgutil_http")
    if bgutil_http_mod is not None:
        if hasattr(bgutil_http_mod, "BgUtilHTTPPTP"):
            bgutil_http_mod.BgUtilHTTPPTP._SUPPORTED_CLIENTS = extended
        if hasattr(bgutil_http_mod, "get_webpo_content_binding"):
            bgutil_http_mod.get_webpo_content_binding = _patched_content_binding


_enable_extended_pot_clients()


def _detect_internal_warp_proxy() -> ProxyEntry | None:
    """Detect if the optional internal Cloudflare WARP SOCKS5 container (warp:1080) is reachable."""
    try:
        with socket.create_connection(("warp", 1080), timeout=0.15):
            return ProxyEntry(url="socks5h://warp:1080", label="warp:1080")
    except OSError:
        return None


class MediaExtractor:
    """
    Executes yt-dlp resolve and download operations safely in worker threads with:
    - L2: curl_cffi browser impersonation (no conflicting UA header)
    - L3: YouTube PO token sidecar + automatic player_client fallback chain
    - L4: Optional hot-reloaded Netscape cookies (used as fallback or primary if needed)
    - L5: Egress proxy pool with automatic failover and ejection
    - L6: Circuit breaker + jittered backoff
    - L7: Typed error classification + strategy escalation (next client -> next proxy -> cookies)
    """

    def __init__(
        self,
        settings: Settings,
        cookie_manager: CookieManager,
        proxy_pool: ProxyPool,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        self._settings = settings
        self._cookies = cookie_manager
        self._proxies = proxy_pool
        self._cb = circuit_breaker

    def _build_attempt_plans(
        self,
        platform: Platform,
        sticky_key: str,
    ) -> list[AttemptPlan]:
        """
        Build a bounded, ordered recovery matrix:
        1. Primary player client (or default for non-YT), primary proxy (or direct), impersonate on.
        2. For YouTube: rotate through configured player_clients (web_safari -> tv -> mweb -> web -> android_vr).
        3. Rotate to alternate healthy proxy if configured.
        4. Try with user-supplied platform cookies if configured and not yet used.
        """
        plans: list[AttemptPlan] = []
        impersonate_default = self._settings.impersonate_enabled and is_curl_cffi_available()
        cookie_available = self._cookies.get_cookie_path(platform) is not None

        primary_proxy = self._proxies.select(platform, sticky_key=sticky_key)
        exclude_set = {primary_proxy.url} if primary_proxy else set()
        backup_proxy = self._proxies.select(platform, sticky_key=f"{sticky_key}:alt", exclude=exclude_set)
        if backup_proxy is None and primary_proxy is None:
            backup_proxy = _detect_internal_warp_proxy()

        if platform == Platform.YOUTUBE:
            clients = self._settings.youtube_client_list or [
                "android_vr",
                "mweb",
                "tv_simply",
                "web_safari",
                "ios",
                "web_embedded",
                "default",
            ]
            # Step 1: iterate player_clients on primary proxy (or direct)
            active_clients = clients[:6]
            for idx, client in enumerate(active_clients):
                plans.append(
                    AttemptPlan(
                        player_client=client,
                        proxy=primary_proxy,
                        use_cookies=(cookie_available and idx == len(active_clients) - 1),
                        use_impersonate=(impersonate_default and client in {"web", "mweb", "web_embedded"}),
                        skip_webpage=False,
                    )
                )
                # Add a webpage-less InnerTube fallback right after android_vr in case /watch HTML is challenged
                if client == "android_vr" and idx == 0:
                    plans.append(
                        AttemptPlan(
                            player_client="android_vr",
                            proxy=primary_proxy,
                            use_cookies=False,
                            use_impersonate=False,
                            skip_webpage=True,
                        )
                    )
            # Step 2: if backup proxy (or WARP sidecar) exists, retry best clients on backup proxy
            if backup_proxy is not None:
                for b_client in active_clients[:2]:
                    plans.append(
                        AttemptPlan(
                            player_client=b_client,
                            proxy=backup_proxy,
                            use_cookies=cookie_available,
                            use_impersonate=(impersonate_default and b_client in {"web", "mweb", "web_embedded"}),
                        )
                    )
            # Step 3: if primary_proxy was configured and failed, also allow direct fallback
            elif primary_proxy is not None:
                plans.append(
                    AttemptPlan(
                        player_client=active_clients[0],
                        proxy=None,
                        use_cookies=cookie_available,
                        use_impersonate=False,
                    )
                )
            # Step 4: if cookies exist and haven't been tried with web client yet
            if cookie_available and not any(p.use_cookies and p.player_client == "web" for p in plans):
                plans.append(
                    AttemptPlan(
                        player_client="web",
                        proxy=primary_proxy,
                        use_cookies=True,
                        use_impersonate=impersonate_default,
                    )
                )
        else:
            # X, Instagram, Facebook: impersonate Chrome first (L2)
            plans.append(
                AttemptPlan(
                    player_client=None,
                    proxy=primary_proxy,
                    use_cookies=False,
                    use_impersonate=impersonate_default,
                )
            )
            if backup_proxy is not None:
                plans.append(
                    AttemptPlan(
                        player_client=None,
                        proxy=backup_proxy,
                        use_cookies=False,
                        use_impersonate=impersonate_default,
                    )
                )
            if cookie_available:
                plans.append(
                    AttemptPlan(
                        player_client=None,
                        proxy=primary_proxy,
                        use_cookies=True,
                        use_impersonate=impersonate_default,
                    )
                )
            # Fallback without impersonate in case curl_cffi target has an upstream quirk
            if impersonate_default:
                plans.append(
                    AttemptPlan(
                        player_client=None,
                        proxy=backup_proxy or primary_proxy,
                        use_cookies=cookie_available,
                        use_impersonate=False,
                    )
                )

        return plans

    def _base_ydl_opts(self, platform: Platform, plan: AttemptPlan) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "nocolor": True,
            "socket_timeout": self._settings.ytdlp_socket_timeout,
            "retries": self._settings.ytdlp_retries,
            "fragment_retries": self._settings.ytdlp_fragment_retries,
            "buffersize": self._settings.ytdlp_buffer_size,
            "http_chunk_size": self._settings.ytdlp_http_chunk_size,
            "concurrent_fragment_downloads": self._settings.ytdlp_concurrent_fragments,
            "allowed_extractors": ALLOWED_YTDLP_EXTRACTORS[platform],
            "geo_bypass": True,
            "no_color": True,
            # Realistic Accept-Language header without overriding impersonated User-Agent
            "http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        if self._settings.ytdlp_force_ipv4:
            opts["source_address"] = "0.0.0.0"

        if plan.use_impersonate:
            target = _resolve_impersonate_target(self._settings.impersonate_target)
            if target is not None:
                opts["impersonate"] = target

        if plan.proxy is not None:
            opts["proxy"] = plan.proxy.url

        if plan.use_cookies:
            cookie_file = self._cookies.get_cookie_path(platform)
            if cookie_file:
                opts["cookiefile"] = cookie_file

        extractor_args: dict[str, dict[str, list[str]]] = {}
        if platform == Platform.YOUTUBE:
            yt_args: dict[str, list[str]] = {}
            if plan.player_client and plan.player_client != "default":
                yt_args["player_client"] = [plan.player_client]

            if self._settings.pot_provider_enabled and self._settings.pot_provider_url:
                yt_args["fetch_pot"] = ["always"]
                if plan.skip_webpage:
                    yt_args["player_skip"] = ["webpage", "configs"]
                else:
                    yt_args["webpage_skip"] = ["player_response"]
                extractor_args["youtubepot-bgutilhttp"] = {"base_url": [self._settings.pot_provider_url]}

            if yt_args:
                extractor_args["youtube"] = yt_args

        if extractor_args:
            opts["extractor_args"] = extractor_args

        return opts

    def _check_media_constraints(self, info: dict[str, Any]) -> None:
        if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
            raise AppError(
                code=ErrorCode.LIVE_STREAM,
                message="Active live streams and upcoming premieres are not supported.",
                hint="Wait until the broadcast finishes and download the replay.",
                retryable=False,
                status_code=422,
            )

        if info.get("has_drm") or any(isinstance(f, dict) and f.get("has_drm") for f in (info.get("formats") or [])):
            # Only reject if ALL formats are DRM-protected
            fmts = [f for f in (info.get("formats") or []) if isinstance(f, dict)]
            if not fmts or all(f.get("has_drm") for f in fmts):
                raise AppError(
                    code=ErrorCode.DRM_PROTECTED,
                    message="This video is DRM-protected and cannot be downloaded.",
                    hint="Only public, non-DRM media is supported.",
                    retryable=False,
                    status_code=422,
                )

        duration = info.get("duration")
        if isinstance(duration, (int, float)) and duration > self._settings.max_duration_seconds:
            max_min = self._settings.max_duration_seconds // 60
            raise AppError(
                code=ErrorCode.TOO_LONG,
                message=f"Video exceeds the maximum supported duration ({max_min} minutes).",
                hint="Try a shorter video.",
                retryable=False,
                status_code=422,
            )

    async def resolve(
        self,
        *,
        url: str,
        normalized_url: str,
        platform: Platform,
    ) -> ResolveResponse:
        """Fast metadata & format resolution (~1-3s typical) with layered anti-block retry."""
        started = time.perf_counter()

        # Fast-path for X (Twitter) via api.fxtwitter.com (works even when api.x.com is blocked by LAN/ISP)
        if platform == Platform.X:
            primary_proxy = self._proxies.select(platform, sticky_key=normalized_url)
            try:
                fx_info = await fetch_fxtwitter_info(
                    normalized_url,
                    proxy=primary_proxy.url if primary_proxy else None,
                )
                formats = parse_formats(fx_info)
                if formats:
                    presets = build_presets(formats)
                    _, _, entries = parse_entries(fx_info, max_items=self._settings.max_playlist_items)
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    return ResolveResponse(
                        url=url,
                        normalized_url=normalized_url,
                        platform=platform,
                        id=str(fx_info["id"]),
                        title=str(fx_info["title"]),
                        uploader=str(fx_info.get("uploader") or "") or None,
                        duration_seconds=int(fx_info["duration"])
                        if isinstance(fx_info.get("duration"), (int, float))
                        else None,
                        thumbnail_url=str(fx_info["thumbnail"]) if fx_info.get("thumbnail") else None,
                        is_playlist=False,
                        is_carousel=len(entries) > 1,
                        entries=entries,
                        presets=presets,
                        formats=formats,
                        subtitles=[],
                        cached=False,
                        resolve_ms=elapsed_ms,
                    )
            except AppError as exc:
                if exc.code in {ErrorCode.REMOVED, ErrorCode.PRIVATE, ErrorCode.UNSUPPORTED, ErrorCode.INVALID_URL}:
                    raise
                logger.info("fxtwitter fast-path unavailable (%s); falling back to yt-dlp", exc.code.value)
            except Exception as exc:
                logger.info("fxtwitter fast-path error (%s); falling back to yt-dlp", exc)

        plans = self._build_attempt_plans(platform, sticky_key=normalized_url)
        last_error: AppError | None = None

        for idx, plan in enumerate(plans):
            proxy_label = plan.proxy.label if plan.proxy else "direct"
            await self._cb.assert_closed(platform, proxy_label)

            if idx > 0:
                await backoff_sleep(idx - 1, base_seconds=0.4, max_seconds=3.0)
            else:
                await jitter_sleep(self._settings.jitter_min_ms, self._settings.jitter_max_ms)

            opts = self._base_ydl_opts(platform, plan)
            opts.update(
                {
                    "skip_download": True,
                    "extract_flat": "in_playlist",
                    "playlistend": self._settings.max_playlist_items,
                    "writesubtitles": False,
                    "writeautomaticsub": False,
                    "writethumbnail": False,
                    "ignoreerrors": False,
                    "noplaylist": False,
                }
            )

            try:
                info = await asyncio.to_thread(self._extract_info_sync, normalized_url, opts, False)
            except Exception as exc:
                err = classify_ytdlp_error(exc)
                last_error = err
                EXTRACTION_FAILURES.labels(
                    error_code=err.code.value,
                    platform=platform.value,
                    proxy=proxy_label,
                ).inc()
                logger.warning(
                    "Resolve attempt %d/%d failed: code=%s client=%s proxy=%s cookies=%s",
                    idx + 1,
                    len(plans),
                    err.code.value,
                    plan.player_client or "default",
                    proxy_label,
                    plan.use_cookies,
                    extra={"platform": platform.value, "error_code": err.code.value, "proxy": proxy_label},
                )
                if plan.use_cookies and is_auth_failure(err):
                    self._cookies.mark_expired(platform)
                if plan.proxy and is_proxy_failure(err):
                    self._proxies.record_failure(platform, plan.proxy.url)
                can_rotate_client = (
                    err.code in {ErrorCode.UNSUPPORTED, ErrorCode.EXTRACTION_FAILED} and idx < len(plans) - 1
                )
                if not err.retryable and not can_rotate_client:
                    raise err from exc
                continue

            if not isinstance(info, dict):
                last_error = AppError(
                    code=ErrorCode.UNSUPPORTED,
                    message="No downloadable media metadata returned.",
                    hint="Confirm the link points to a public video.",
                    status_code=422,
                )
                continue

            # Check playlist/carousel entries
            is_playlist, is_carousel, entries = parse_entries(info, max_items=self._settings.max_playlist_items)

            # If single-item video (or carousel where first item has formats), check constraints
            target_info = info
            if is_carousel and entries and not info.get("formats"):
                first_raw = (info.get("entries") or [None])[0]
                if isinstance(first_raw, dict):
                    target_info = first_raw

            if not is_playlist:
                self._check_media_constraints(target_info)

            formats = parse_formats(target_info)
            # If attempt returned zero formats (common on soft-blocked client), rotate to next plan
            if not is_playlist and not formats and idx < len(plans) - 1:
                logger.info(
                    "Attempt %d/%d on %s (client=%s) returned 0 formats; rotating to next plan",
                    idx + 1,
                    len(plans),
                    platform.value,
                    plan.player_client or "default",
                    extra={"platform": platform.value},
                )
                continue

            # Success! Record health
            if plan.proxy:
                self._proxies.record_success(platform, plan.proxy.url)
            await self._cb.record_success(platform, proxy_label)

            presets = build_presets(formats)
            subtitles = parse_subtitles(target_info)
            elapsed_ms = int((time.perf_counter() - started) * 1000)

            thumbnail = target_info.get("thumbnail")
            if not thumbnail and isinstance(target_info.get("thumbnails"), list) and target_info["thumbnails"]:
                thumbnail = target_info["thumbnails"][-1].get("url")

            duration_val = target_info.get("duration")
            return ResolveResponse(
                url=url,
                normalized_url=normalized_url,
                platform=platform,
                id=str(target_info.get("id") or info.get("id") or "media"),
                title=str(target_info.get("title") or info.get("title") or "Untitled Video"),
                uploader=str(target_info.get("uploader") or target_info.get("channel") or "") or None,
                duration_seconds=int(duration_val) if isinstance(duration_val, (int, float)) else None,
                thumbnail_url=str(thumbnail) if thumbnail else None,
                is_playlist=is_playlist,
                is_carousel=is_carousel,
                entries=entries,
                presets=presets,
                formats=formats,
                subtitles=subtitles,
                cached=False,
                resolve_ms=elapsed_ms,
            )

        if last_error is not None and last_error.code == ErrorCode.RATE_LIMITED:
            await self._cb.record_failure(platform, "direct")

        raise last_error or AppError(
            code=ErrorCode.EXTRACTION_FAILED,
            message="Failed to resolve video after all recovery attempts.",
            hint="Please try again later.",
            retryable=True,
            status_code=502,
        )

    async def download(
        self,
        *,
        job_id: str,
        normalized_url: str,
        platform: Platform,
        preset: Preset | None,
        format_id: str | None,
        audio_format: str | None,
        subtitle_lang: str | None,
        download_thumbnail: bool,
        playlist_item: int | None,
        work_dir: Path,
        on_progress: Callable[[dict[str, Any]], None],
        is_cancelled: Callable[[], bool],
    ) -> DownloadArtifact:
        """Download and remux media into `work_dir` using stream copy (-c copy) whenever possible."""
        if platform == Platform.X:
            primary_proxy = self._proxies.select(platform, sticky_key=job_id)
            try:
                fx_media_path, fx_ext, fx_title, fx_thumb_path = await download_fxtwitter_video(
                    normalized_url=normalized_url,
                    preset=preset,
                    format_id=format_id,
                    audio_format=audio_format,
                    download_thumbnail=download_thumbnail,
                    playlist_item=playlist_item,
                    work_dir=work_dir,
                    proxy=primary_proxy.url if primary_proxy else None,
                    max_filesize_bytes=self._settings.max_filesize_bytes,
                    on_progress=on_progress,
                    is_cancelled=is_cancelled,
                    cancel_exc_cls=DownloadCancelledError,
                )
                return DownloadArtifact(
                    media_path=fx_media_path,
                    filename=sanitize_filename(fx_title, fx_ext),
                    ext=fx_ext,
                    title=fx_title,
                    filesize_bytes=fx_media_path.stat().st_size,
                    subtitle_path=None,
                    thumbnail_path=fx_thumb_path,
                )
            except DownloadCancelledError:
                raise
            except AppError as exc:
                if exc.code in {ErrorCode.TOO_LARGE, ErrorCode.REMOVED, ErrorCode.PRIVATE, ErrorCode.UNSUPPORTED}:
                    raise
                logger.info("fxtwitter download fallback to yt-dlp after: %s", exc.code.value)
            except Exception as exc:
                logger.info("fxtwitter download fallback to yt-dlp after error: %s", exc)

        plans = self._build_attempt_plans(platform, sticky_key=job_id)
        fmt_opts = build_ytdlp_format_options(
            platform=platform,
            preset=preset,
            format_id=format_id,
            audio_format=audio_format,
        )
        last_error: AppError | None = None

        for idx, plan in enumerate(plans):
            if is_cancelled():
                raise DownloadCancelledError("Job cancelled before download attempt")

            proxy_label = plan.proxy.label if plan.proxy else "direct"
            await self._cb.assert_closed(platform, proxy_label)

            if idx > 0:
                await backoff_sleep(idx - 1, base_seconds=0.8, max_seconds=5.0)
                await asyncio.to_thread(self._clear_work_dir, work_dir)
            else:
                await jitter_sleep(self._settings.jitter_min_ms, self._settings.jitter_max_ms)

            opts = self._base_ydl_opts(platform, plan)
            opts.update(fmt_opts)
            opts.update(
                {
                    "outtmpl": str(work_dir / "media.%(ext)s"),
                    "overwrites": True,
                    "noplaylist": playlist_item is None,
                    "max_filesize": self._settings.max_filesize_bytes,
                    # Ensure ffmpeg uses stream copy when merging video+audio (never re-encode)
                    "postprocessor_args": {
                        "Merger+ffmpeg": ["-c", "copy", "-movflags", "+faststart"],
                    },
                }
            )

            if playlist_item is not None:
                opts["playlist_items"] = str(playlist_item)

            if subtitle_lang:
                opts["writesubtitles"] = True
                opts["writeautomaticsub"] = True
                opts["subtitleslangs"] = [subtitle_lang]
                opts["subtitlesformat"] = "srt/vtt/best"
                pps = list(opts.get("postprocessors") or [])
                pps.append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})
                opts["postprocessors"] = pps

            if download_thumbnail:
                opts["writethumbnail"] = True

            # Optional aria2c accelerator for direct-HTTP formats (not used with cookies/impersonate mismatch)
            if self._settings.enable_aria2c and is_aria2c_available() and not plan.use_impersonate:
                opts["external_downloader"] = {"default": "aria2c"}
                opts["external_downloader_args"] = {
                    "aria2c": [
                        f"-x{self._settings.aria2c_connections}",
                        f"-s{self._settings.aria2c_splits}",
                        f"-k{self._settings.aria2c_min_split_size}",
                        "--summary-interval=1",
                    ]
                }

            def _progress_hook(d: dict[str, Any]) -> None:
                if is_cancelled():
                    raise DownloadCancelledError("Job cancelled by user")
                on_progress(d)

            def _postprocessor_hook(d: dict[str, Any]) -> None:
                if is_cancelled():
                    raise DownloadCancelledError("Job cancelled by user")
                if d.get("status") == "started":
                    on_progress({"status": "merging", "postprocessor": d.get("postprocessor", "ffmpeg")})

            opts["progress_hooks"] = [_progress_hook]
            opts["postprocessor_hooks"] = [_postprocessor_hook]

            try:
                info = await asyncio.to_thread(self._extract_info_sync, normalized_url, opts, True)
            except DownloadCancelledError:
                raise
            except Exception as exc:
                err = classify_ytdlp_error(exc)
                last_error = err
                EXTRACTION_FAILURES.labels(
                    error_code=err.code.value,
                    platform=platform.value,
                    proxy=proxy_label,
                ).inc()
                logger.warning(
                    "Download attempt %d/%d failed: job=%s code=%s client=%s proxy=%s",
                    idx + 1,
                    len(plans),
                    job_id,
                    err.code.value,
                    plan.player_client or "default",
                    proxy_label,
                    extra={
                        "job_id": job_id,
                        "platform": platform.value,
                        "error_code": err.code.value,
                        "proxy": proxy_label,
                    },
                )
                if plan.use_cookies and is_auth_failure(err):
                    self._cookies.mark_expired(platform)
                if plan.proxy and is_proxy_failure(err):
                    self._proxies.record_failure(platform, plan.proxy.url)
                can_rotate_client = (
                    err.code in {ErrorCode.UNSUPPORTED, ErrorCode.EXTRACTION_FAILED} and idx < len(plans) - 1
                )
                if not err.retryable and not can_rotate_client:
                    raise err from exc
                continue

            if plan.proxy:
                self._proxies.record_success(platform, plan.proxy.url)
            await self._cb.record_success(platform, proxy_label)

            # Locate downloaded primary media file, optional subtitle, optional thumbnail
            target_info = info
            if isinstance(info, dict) and isinstance(info.get("entries"), list) and info["entries"]:
                first = next((e for e in info["entries"] if isinstance(e, dict)), None)
                if first:
                    target_info = first

            media_path = self._find_primary_media_file(work_dir)
            if media_path is None or not media_path.exists():
                last_error = AppError(
                    code=ErrorCode.EXTRACTION_FAILED,
                    message="Download finished but no output media file was produced.",
                    hint="Try choosing 'Best Compatible (MP4)' or another format.",
                    retryable=True,
                    status_code=500,
                )
                continue

            file_size = media_path.stat().st_size
            if file_size > self._settings.max_filesize_bytes:
                media_path.unlink(missing_ok=True)
                max_mb = self._settings.max_filesize_bytes // (1024 * 1024)
                raise AppError(
                    code=ErrorCode.TOO_LARGE,
                    message=f"Output file exceeds the {max_mb} MB limit.",
                    hint="Choose a lower resolution preset (e.g., 1080p or 720p).",
                    retryable=False,
                    status_code=422,
                )

            title = str(target_info.get("title") or "video") if isinstance(target_info, dict) else "video"
            ext = media_path.suffix.lstrip(".").lower() or "mp4"
            safe_filename = sanitize_filename(title, ext)

            sub_path = self._find_optional_file(work_dir, {".srt", ".vtt"})
            thumb_path = self._find_optional_file(work_dir, {".jpg", ".jpeg", ".png", ".webp"})

            return DownloadArtifact(
                media_path=media_path,
                filename=safe_filename,
                ext=ext,
                title=title,
                filesize_bytes=file_size,
                subtitle_path=sub_path,
                thumbnail_path=thumb_path,
            )

        if last_error is not None and last_error.code == ErrorCode.RATE_LIMITED:
            await self._cb.record_failure(platform, "direct")

        raise last_error or AppError(
            code=ErrorCode.EXTRACTION_FAILED,
            message="Download failed after all recovery strategies.",
            hint="Please retry shortly.",
            retryable=True,
            status_code=502,
        )

    @staticmethod
    def _clear_work_dir(work_dir: Path) -> None:
        for p in work_dir.glob("*"):
            if p.is_file():
                p.unlink(missing_ok=True)

    @staticmethod
    def _extract_info_sync(url: str, opts: dict[str, Any], download: bool) -> Any:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)

    @staticmethod
    def _find_primary_media_file(work_dir: Path) -> Path | None:
        media_exts = {".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".opus", ".ogg", ".m4v", ".ts"}
        candidates = [
            p
            for p in work_dir.iterdir()
            if p.is_file() and not p.name.endswith((".part", ".ytdl", ".temp")) and p.suffix.lower() in media_exts
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
        return candidates[0]

    @staticmethod
    def _find_optional_file(work_dir: Path, exts: set[str]) -> Path | None:
        candidates = [p for p in work_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
        return candidates[0]
