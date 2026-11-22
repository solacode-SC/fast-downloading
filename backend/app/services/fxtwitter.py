"""Fast, resilient X (Twitter) media resolver and downloader using api.fxtwitter.com + video.twimg.com."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.errors import AppError, ErrorCode
from app.schemas import Preset

logger = logging.getLogger(__name__)

_TWEET_ID_RE = re.compile(r"/(?:status|statuses)/(\d+)")
_RES_FROM_URL_RE = re.compile(r"/(\d{2,4})x(\d{2,4})/")
_ALLOWED_MEDIA_HOSTS = ("twimg.com", "video.twimg.com", "pbs.twimg.com")


def extract_tweet_id(url: str) -> str | None:
    match = _TWEET_ID_RE.search(url)
    return match.group(1) if match else None


def is_safe_twimg_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        host = (parsed.hostname or "").lower().rstrip(".")
        return any(host == d or host.endswith(f".{d}") for d in _ALLOWED_MEDIA_HOSTS)
    except Exception:
        return False


def _parse_video_formats(video: dict[str, Any], duration: float | None) -> list[dict[str, Any]]:
    raw_list = video.get("formats") or video.get("variants") or []
    base_w = video.get("width")
    base_h = video.get("height")
    formats: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            continue
        v_url = str(item.get("url") or "").strip()
        if not v_url or v_url in seen_urls or not is_safe_twimg_url(v_url):
            continue
        seen_urls.add(v_url)

        container = str(item.get("container") or "").lower()
        ctype = str(item.get("content_type") or "").lower()
        if container == "m3u8" or "mpegurl" in ctype or ".m3u8" in v_url:
            continue

        bitrate = item.get("bitrate")
        tbr_kbps = round(float(bitrate) / 1000.0, 1) if isinstance(bitrate, (int, float)) and bitrate > 0 else None

        w: int | None = None
        h: int | None = None
        res_match = _RES_FROM_URL_RE.search(v_url)
        if res_match:
            w = int(res_match.group(1))
            h = int(res_match.group(2))
        elif isinstance(base_w, int) and isinstance(base_h, int):
            w, h = base_w, base_h

        est_size: int | None = None
        if tbr_kbps and duration and duration > 0:
            est_size = int((tbr_kbps * 1000.0 / 8.0) * duration)

        fmt_id = f"http-{int(tbr_kbps)}" if tbr_kbps else f"mp4-{idx + 1}"
        formats.append(
            {
                "format_id": fmt_id,
                "url": v_url,
                "ext": "mp4",
                "width": w,
                "height": h,
                "vcodec": "avc1",
                "acodec": "mp4a.40.2",
                "tbr": tbr_kbps,
                "filesize_approx": est_size,
            }
        )

    # Fallback to top-level video.url if variants list had no direct mp4
    top_url = str(video.get("url") or "").strip()
    if not formats and top_url and is_safe_twimg_url(top_url) and ".m3u8" not in top_url:
        formats.append(
            {
                "format_id": "http-best",
                "url": top_url,
                "ext": "mp4",
                "width": int(base_w) if isinstance(base_w, int) else None,
                "height": int(base_h) if isinstance(base_h, int) else None,
                "vcodec": "avc1",
                "acodec": "mp4a.40.2",
                "tbr": None,
                "filesize_approx": None,
            }
        )

    formats.sort(key=lambda f: (f.get("height") or 0, f.get("tbr") or 0.0), reverse=True)
    return formats


async def fetch_fxtwitter_info(
    normalized_url: str,
    *,
    proxy: str | None = None,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Fetch tweet metadata and direct MP4 variants from api.fxtwitter.com."""
    tweet_id = extract_tweet_id(normalized_url)
    if not tweet_id:
        raise AppError(
            code=ErrorCode.INVALID_URL,
            message="Please enter a direct X (Twitter) post URL containing /status/<id>.",
            hint="Example: https://x.com/username/status/1234567890",
            status_code=400,
        )

    api_url = f"https://api.fxtwitter.com/status/{tweet_id}"
    client_kwargs: dict[str, Any] = {
        "timeout": timeout_seconds,
        "follow_redirects": True,
        "headers": {
            "User-Agent": "FastDL/1.0 (+https://github.com/fastdl)",
            "Accept": "application/json",
        },
    }
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        resp = await client.get(api_url)

    if resp.status_code == 404:
        raise AppError(
            code=ErrorCode.REMOVED,
            message="This X (Twitter) post was not found or has been deleted.",
            hint="Verify that the post is public and still exists.",
            status_code=404,
        )
    if resp.status_code == 401 or resp.status_code == 403:
        raise AppError(
            code=ErrorCode.PRIVATE,
            message="This X (Twitter) post is protected or private.",
            hint="Only public X posts can be downloaded.",
            status_code=403,
        )
    if resp.status_code >= 400:
        raise AppError(
            code=ErrorCode.NETWORK,
            message=f"Upstream X metadata service returned HTTP {resp.status_code}.",
            hint="Please retry in a moment.",
            retryable=True,
            status_code=503,
        )

    payload = resp.json()
    tweet = payload.get("tweet")
    if not isinstance(tweet, dict):
        raise AppError(
            code=ErrorCode.REMOVED,
            message="Tweet metadata is unavailable.",
            hint="Confirm the post is public.",
            status_code=404,
        )

    media = tweet.get("media") or {}
    videos = media.get("videos") or [
        m for m in (media.get("all") or []) if isinstance(m, dict) and m.get("type") in {"video", "gif"}
    ]
    if not videos:
        raise AppError(
            code=ErrorCode.UNSUPPORTED,
            message="No downloadable video or GIF was found in this X post.",
            hint="Make sure the post contains a video or GIF rather than text or images only.",
            status_code=422,
        )

    author = tweet.get("author") or {}
    uploader = str(author.get("name") or author.get("screen_name") or "X User")
    raw_text = str(tweet.get("text") or "").strip()
    clean_text = re.sub(r"https?://\S+", "", raw_text).strip()
    first_line = clean_text.splitlines()[0].strip() if clean_text else ""
    title = first_line[:110] if first_line else f"{uploader} - X Video {tweet_id}"

    primary = videos[0]
    duration = float(primary["duration"]) if isinstance(primary.get("duration"), (int, float)) else None
    thumb = str(primary.get("thumbnail_url") or "") or None
    formats = _parse_video_formats(primary, duration)
    if not formats:
        raise AppError(
            code=ErrorCode.UNSUPPORTED,
            message="No direct MP4 video streams were found for this X post.",
            hint="Try another public video post.",
            status_code=422,
        )

    entries: list[dict[str, Any]] = []
    if len(videos) > 1:
        for idx, vid in enumerate(videos, start=1):
            v_dur = float(vid["duration"]) if isinstance(vid.get("duration"), (int, float)) else None
            entries.append(
                {
                    "id": str(vid.get("id") or f"{tweet_id}_{idx}"),
                    "title": f"{title} ({idx}/{len(videos)})",
                    "webpage_url": normalized_url,
                    "duration": v_dur,
                    "thumbnail": vid.get("thumbnail_url") or thumb,
                    "formats": _parse_video_formats(vid, v_dur),
                }
            )

    return {
        "id": tweet_id,
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "thumbnail": thumb,
        "formats": formats,
        "entries": entries,
        "extractor_key": "Twitter",
    }


def _select_x_variant(
    formats: list[dict[str, Any]],
    preset: Preset | None,
    format_id: str | None,
) -> dict[str, Any]:
    if format_id:
        for f in formats:
            if f.get("format_id") == format_id:
                return f

    height_caps = {
        Preset.P2160: 2160,
        Preset.P1440: 1440,
        Preset.P1080: 1080,
        Preset.P720: 720,
        Preset.P480: 480,
    }
    cap = height_caps.get(preset) if preset else None
    if cap is not None:
        # For vertical videos (e.g. 720x1280), check min(width, height) against cap
        capped = [
            f
            for f in formats
            if min(f.get("width") or 9999, f.get("height") or 9999) <= cap or (f.get("height") or 0) <= cap
        ]
        if capped:
            return capped[0]

    return formats[0]


def _extract_audio_ffmpeg_sync(src_mp4: Path, dst_path: Path, codec: str, bitrate_kbps: str) -> None:
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    if codec == "m4a":
        cmd = [ffmpeg_bin, "-y", "-i", str(src_mp4), "-vn", "-c:a", "copy", str(dst_path)]
    else:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(src_mp4),
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            f"{bitrate_kbps}k",
            str(dst_path),
        ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0 or not dst_path.exists():
        raise AppError(
            code=ErrorCode.EXTRACTION_FAILED,
            message="Failed to extract audio stream from video.",
            hint="Try downloading the MP4 video preset instead.",
            status_code=500,
        )


async def download_fxtwitter_video(
    *,
    normalized_url: str,
    preset: Preset | None,
    format_id: str | None,
    audio_format: str | None,
    download_thumbnail: bool,
    playlist_item: int | None,
    work_dir: Path,
    proxy: str | None,
    max_filesize_bytes: int,
    on_progress: Callable[[dict[str, Any]], None],
    is_cancelled: Callable[[], bool],
    cancel_exc_cls: type[Exception],
) -> tuple[Path, str, str, Path | None]:
    """
    Download the selected X/Twitter MP4 variant directly from video.twimg.com with
    live progress callbacks, optional audio extraction, and optional thumbnail download.
    Returns (media_path, ext, title, thumbnail_path).
    """
    info = await fetch_fxtwitter_info(normalized_url, proxy=proxy)
    target = info
    entries = info.get("entries") or []
    if playlist_item and entries and 1 <= playlist_item <= len(entries):
        target = entries[playlist_item - 1]

    formats = target.get("formats") or info.get("formats") or []
    chosen = _select_x_variant(formats, preset, format_id)
    stream_url = str(chosen["url"])
    if not is_safe_twimg_url(stream_url):
        raise AppError(
            code=ErrorCode.SSRF_BLOCKED,
            message="Blocked untrusted media host.",
            hint="Only official twimg.com media streams are permitted.",
            status_code=403,
        )

    mp4_path = work_dir / "media.mp4"
    client_kwargs: dict[str, Any] = {"timeout": 30.0, "follow_redirects": True}
    if proxy:
        client_kwargs["proxy"] = proxy

    import time

    t0 = time.perf_counter()
    downloaded = 0

    async with httpx.AsyncClient(**client_kwargs) as client, client.stream("GET", stream_url) as resp:
        if resp.status_code >= 400:
            raise AppError(
                code=ErrorCode.NETWORK,
                message=f"Could not download video stream (HTTP {resp.status_code}).",
                hint="Please retry shortly.",
                retryable=True,
                status_code=503,
            )
        cl = resp.headers.get("content-length")
        total_bytes = int(cl) if cl and cl.isdigit() else chosen.get("filesize_approx")
        if total_bytes and total_bytes > max_filesize_bytes:
            raise AppError(
                code=ErrorCode.TOO_LARGE,
                message="Video exceeds maximum allowed file size.",
                hint="Choose a smaller resolution variant.",
                status_code=422,
            )

        with mp4_path.open("wb") as f:
            async for chunk in resp.aiter_bytes(chunk_size=65_536):
                if is_cancelled():
                    raise cancel_exc_cls("Job cancelled by user")
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > max_filesize_bytes:
                    raise AppError(
                        code=ErrorCode.TOO_LARGE,
                        message="Video exceeds maximum allowed file size.",
                        hint="Choose a lower resolution.",
                        status_code=422,
                    )
                elapsed = max(0.05, time.perf_counter() - t0)
                speed = downloaded / elapsed
                eta = int((total_bytes - downloaded) / speed) if (total_bytes and speed > 0) else 0
                on_progress(
                    {
                        "status": "downloading",
                        "downloaded_bytes": downloaded,
                        "total_bytes": total_bytes,
                        "speed": speed,
                        "eta": max(0, eta),
                    }
                )

    effective_preset = preset or Preset.BEST
    if audio_format == "m4a":
        effective_preset = Preset.AUDIO_M4A
    elif audio_format == "mp3_192":
        effective_preset = Preset.AUDIO_MP3_192
    elif audio_format == "mp3_320":
        effective_preset = Preset.AUDIO_MP3_320

    final_path = mp4_path
    final_ext = "mp4"
    if effective_preset in {Preset.AUDIO_M4A, Preset.AUDIO_MP3_192, Preset.AUDIO_MP3_320}:
        on_progress({"status": "merging", "postprocessor": "ffmpeg"})
        if effective_preset == Preset.AUDIO_M4A:
            final_ext = "m4a"
            final_path = work_dir / "media.m4a"
            await asyncio.to_thread(_extract_audio_ffmpeg_sync, mp4_path, final_path, "m4a", "0")
        else:
            br = "320" if effective_preset == Preset.AUDIO_MP3_320 else "192"
            final_ext = "mp3"
            final_path = work_dir / "media.mp3"
            await asyncio.to_thread(_extract_audio_ffmpeg_sync, mp4_path, final_path, "mp3", br)
        mp4_path.unlink(missing_ok=True)

    thumb_path: Path | None = None
    thumb_url = str(target.get("thumbnail") or info.get("thumbnail") or "")
    if download_thumbnail and thumb_url and is_safe_twimg_url(thumb_url):
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                t_resp = await client.get(thumb_url)
                if t_resp.status_code == 200:
                    thumb_path = work_dir / "thumb.jpg"
                    thumb_path.write_bytes(t_resp.content)
        except Exception as exc:
            logger.debug("Optional X thumbnail download skipped: %s", exc)

    return final_path, final_ext, str(target.get("title") or info["title"]), thumb_path
