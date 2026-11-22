"""arq worker tasks: download execution, per-host semaphore, progress publishing, cleanup, updater, canary."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.config import Settings
from app.errors import AppError, ErrorCode, classify_ytdlp_error
from app.metrics import ACTIVE_JOBS, JOB_DURATION, JOBS_TOTAL, QUEUE_DEPTH
from app.schemas import JobStatus, Platform, Preset
from app.security.ratelimit import RateLimiter
from app.security.sanitize import sanitize_filename
from app.security.tokens import create_download_token
from app.services.canary import run_canary_checks
from app.services.extractor import DownloadCancelledError, MediaExtractor
from app.services.job_store import JobStore
from app.services.storage import StorageManager
from app.services.updater import update_ytdlp_with_rollback

logger = logging.getLogger(__name__)


async def download_job_task(
    ctx: dict[str, Any],
    *,
    job_id: str,
    normalized_url: str,
    platform_str: str,
    preset_str: str | None,
    format_id: str | None,
    audio_format: str | None,
    subtitle_lang: str | None,
    download_thumbnail: bool,
    playlist_item: int | None,
    client_ip: str,
    idem_key: str,
) -> dict[str, Any]:
    """Execute a queued video download job with per-platform concurrency limiting and live SSE progress."""
    settings: Settings = ctx["settings"]
    store: JobStore = ctx["job_store"]
    extractor: MediaExtractor = ctx["extractor"]
    storage: StorageManager = ctx["storage"]
    limiter: RateLimiter = ctx["rate_limiter"]
    semaphores: dict[Platform, asyncio.Semaphore] = ctx["platform_semaphores"]

    platform = Platform(platform_str)
    preset = Preset(preset_str) if preset_str else None
    started = time.perf_counter()

    snapshot = await store.get_job(job_id)
    if snapshot is None:
        return {"status": "missing", "job_id": job_id}

    # Check if already cancelled while sitting in queue
    if await store.is_cancelled(job_id) or snapshot.status == JobStatus.CANCELLED:
        snapshot.status = JobStatus.CANCELLED
        await store.save_job(snapshot)
        storage.cleanup_job(job_id)
        await limiter.release_ip_job(client_ip, job_id)
        await store.clear_idempotent_job(idem_key)
        return {"status": "cancelled", "job_id": job_id}

    sem = semaphores[platform]
    cancel_flag = {"cancelled": False}

    # Background task polling Redis cancel flag so running yt-dlp hook aborts within 0.5s
    async def _watch_cancel() -> None:
        while True:
            await asyncio.sleep(0.5)
            if await store.is_cancelled(job_id):
                cancel_flag["cancelled"] = True
                return

    watcher = asyncio.create_task(_watch_cancel())
    loop = asyncio.get_running_loop()
    last_publish = {"ts": 0.0}

    def _on_progress(d: dict[str, Any]) -> None:
        now = time.perf_counter()
        status = d.get("status")
        if status == "merging":
            snapshot.status = JobStatus.MERGING
            snapshot.progress_percent = 99.0
            snapshot.phase_detail = "Merging audio & video streams (stream copy)..."
            asyncio.run_coroutine_threadsafe(store.save_job(snapshot), loop)
            return

        if status == "downloading":
            # Throttle Redis pubsub publishes to ~4 Hz
            if now - last_publish["ts"] < 0.25:
                return
            last_publish["ts"] = now

            downloaded = int(d.get("downloaded_bytes") or 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            total_int = int(total) if isinstance(total, (int, float)) and total > 0 else None
            pct = 0.0
            if total_int:
                pct = min(98.5, round((downloaded / total_int) * 100.0, 1))
            elif (
                isinstance(d.get("fragment_index"), int)
                and isinstance(d.get("fragment_count"), int)
                and d["fragment_count"] > 0
            ):
                pct = min(98.5, round((d["fragment_index"] / d["fragment_count"]) * 100.0, 1))

            speed = d.get("speed")
            eta = d.get("eta")
            snapshot.status = JobStatus.DOWNLOADING
            snapshot.downloaded_bytes = downloaded
            snapshot.total_bytes = total_int
            snapshot.progress_percent = pct
            snapshot.speed_bytes_per_sec = float(speed) if isinstance(speed, (int, float)) else None
            snapshot.eta_seconds = int(eta) if isinstance(eta, (int, float)) else None
            snapshot.phase_detail = "Downloading media streams..."
            asyncio.run_coroutine_threadsafe(store.save_job(snapshot), loop)

    ACTIVE_JOBS.labels(platform=platform.value).inc()
    try:
        async with sem:
            storage.assert_disk_quota()

            snapshot.status = JobStatus.DOWNLOADING
            snapshot.phase_detail = "Starting extraction..."
            await store.save_job(snapshot)

            work_dir = storage.job_work_dir(job_id)
            artifact = await extractor.download(
                job_id=job_id,
                normalized_url=normalized_url,
                platform=platform,
                preset=preset,
                format_id=format_id,
                audio_format=audio_format,
                subtitle_lang=subtitle_lang,
                download_thumbnail=download_thumbnail,
                playlist_item=playlist_item,
                work_dir=work_dir,
                on_progress=_on_progress,
                is_cancelled=lambda: cancel_flag["cancelled"],
            )

            # Move artifacts atomically from tmpfs/work_dir to final storage directory
            final_dir = storage.job_final_dir(job_id)
            final_media = storage.move_atomically(artifact.media_path, final_dir, f"media.{artifact.ext}")
            mime_type = storage.guess_mime(final_media)

            sub_final_path: str | None = None
            sub_filename: str | None = None
            sub_token: str | None = None
            if artifact.subtitle_path and artifact.subtitle_path.exists():
                sub_ext = artifact.subtitle_path.suffix.lstrip(".") or "srt"
                sub_moved = storage.move_atomically(artifact.subtitle_path, final_dir, f"sub.{sub_ext}")
                sub_final_path = str(sub_moved)
                sub_filename = sanitize_filename(artifact.title, sub_ext)
                sub_token = create_download_token(
                    job_id=job_id,
                    kind="subtitle",
                    secret=settings.hmac_secret.get_secret_value(),
                    ttl_seconds=settings.download_token_ttl_seconds,
                )

            thumb_final_path: str | None = None
            thumb_filename: str | None = None
            thumb_token: str | None = None
            if artifact.thumbnail_path and artifact.thumbnail_path.exists():
                th_ext = artifact.thumbnail_path.suffix.lstrip(".") or "jpg"
                th_moved = storage.move_atomically(artifact.thumbnail_path, final_dir, f"thumb.{th_ext}")
                thumb_final_path = str(th_moved)
                thumb_filename = sanitize_filename(artifact.title, th_ext)
                thumb_token = create_download_token(
                    job_id=job_id,
                    kind="thumbnail",
                    secret=settings.hmac_secret.get_secret_value(),
                    ttl_seconds=settings.download_token_ttl_seconds,
                )

            # Remove temporary work directory
            if work_dir.exists():
                import shutil

                shutil.rmtree(work_dir, ignore_errors=True)

            expires_at = time.time() + settings.file_ttl_seconds
            await store.save_artifact_metadata(
                job_id,
                platform=platform,
                media_path=str(final_media),
                media_filename=artifact.filename,
                media_mime=mime_type,
                media_size=artifact.filesize_bytes,
                subtitle_path=sub_final_path,
                subtitle_filename=sub_filename,
                thumbnail_path=thumb_final_path,
                thumbnail_filename=thumb_filename,
                expires_at=expires_at,
            )

            dl_token = create_download_token(
                job_id=job_id,
                kind="media",
                secret=settings.hmac_secret.get_secret_value(),
                ttl_seconds=settings.download_token_ttl_seconds,
            )

            snapshot.status = JobStatus.READY
            snapshot.title = artifact.title
            snapshot.progress_percent = 100.0
            snapshot.downloaded_bytes = artifact.filesize_bytes
            snapshot.total_bytes = artifact.filesize_bytes
            snapshot.eta_seconds = 0
            snapshot.phase_detail = "Ready for download"
            snapshot.download_token = dl_token
            snapshot.download_url = f"/api/v1/files/{dl_token}"
            snapshot.filename = artifact.filename
            snapshot.mime_type = mime_type
            snapshot.filesize_bytes = artifact.filesize_bytes
            snapshot.subtitle_token = sub_token
            snapshot.subtitle_url = f"/api/v1/files/{sub_token}" if sub_token else None
            snapshot.thumbnail_token = thumb_token
            snapshot.thumbnail_url_download = f"/api/v1/files/{thumb_token}" if thumb_token else None
            snapshot.expires_at = expires_at
            await store.save_job(snapshot)

            elapsed = time.perf_counter() - started
            JOBS_TOTAL.labels(platform=platform.value, status="ready").inc()
            JOB_DURATION.labels(platform=platform.value).observe(elapsed)
            logger.info(
                "Download job READY job_id=%s size=%d elapsed=%.2fs",
                job_id,
                artifact.filesize_bytes,
                elapsed,
                extra={
                    "job_id": job_id,
                    "platform": platform.value,
                    "duration_ms": int(elapsed * 1000),
                },
            )
            return {"status": "ready", "job_id": job_id}

    except DownloadCancelledError:
        snapshot.status = JobStatus.CANCELLED
        snapshot.phase_detail = "Cancelled by user"
        snapshot.error = AppError(
            code=ErrorCode.CANCELLED,
            message="Download was cancelled.",
            hint="You can start a new download at any time.",
        ).to_detail()
        await store.save_job(snapshot)
        storage.cleanup_job(job_id)
        await store.clear_idempotent_job(idem_key)
        JOBS_TOTAL.labels(platform=platform.value, status="cancelled").inc()
        return {"status": "cancelled", "job_id": job_id}

    except Exception as exc:
        err = classify_ytdlp_error(exc)
        snapshot.status = JobStatus.FAILED
        snapshot.phase_detail = "Failed"
        snapshot.error = err.to_detail()
        await store.save_job(snapshot)
        storage.cleanup_job(job_id)
        await store.clear_idempotent_job(idem_key)
        JOBS_TOTAL.labels(platform=platform.value, status="failed").inc()
        logger.error(
            "Download job FAILED job_id=%s code=%s msg=%s",
            job_id,
            err.code.value,
            err.message,
            extra={"job_id": job_id, "platform": platform.value, "error_code": err.code.value},
        )
        return {"status": "failed", "job_id": job_id, "error": err.code.value}

    finally:
        watcher.cancel()
        ACTIVE_JOBS.labels(platform=platform.value).dec()
        await limiter.release_ip_job(client_ip, job_id)
        # Update queue depth gauge best-effort
        try:
            redis_client = ctx.get("redis_client")
            if redis_client is not None:
                depth = await redis_client.zcard("arq:queue")
                QUEUE_DEPTH.set(int(depth or 0))
        except Exception as exc:
            logger.debug("Queue depth metric update skipped: %s", exc)


async def cleanup_expired_files_cron(ctx: dict[str, Any]) -> int:
    storage: StorageManager = ctx["storage"]
    return storage.cleanup_expired()


async def daily_ytdlp_update_cron(ctx: dict[str, Any]) -> dict[str, Any]:
    settings: Settings = ctx["settings"]
    if not settings.ytdlp_auto_update:
        return {"skipped": True}
    return await asyncio.to_thread(update_ytdlp_with_rollback, settings)


async def daily_canary_check_cron(ctx: dict[str, Any]) -> dict[str, Any]:
    settings: Settings = ctx["settings"]
    extractor: MediaExtractor = ctx["extractor"]
    if not settings.canary_enabled:
        return {"skipped": True}
    return await run_canary_checks(settings, extractor)
