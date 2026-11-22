"""Job creation, status polling, Server-Sent Events (SSE) progress stream, and cancellation."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_app_state, get_client_ip
from app.errors import AppError, ErrorCode
from app.metrics import QUEUE_DEPTH
from app.schemas import CreateJobRequest, CreateJobResponse, JobSnapshot, JobStatus
from app.security.ssrf import validate_and_resolve_url
from app.security.tokens import create_download_token
from app.security.turnstile import verify_turnstile
from app.services.job_store import make_idempotency_key
from app.services.platforms import detect_platform, normalize_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["jobs"])

_TERMINAL_STATES = {JobStatus.READY, JobStatus.FAILED, JobStatus.CANCELLED}


@router.post("/jobs", response_model=CreateJobResponse, status_code=202)
async def create_job(body: CreateJobRequest, request: Request) -> CreateJobResponse:
    svc = get_app_state(request)
    settings = svc.settings
    client_ip = get_client_ip(request, settings)

    # Optional Cloudflare Turnstile human check
    await verify_turnstile(body.turnstile_token, client_ip, settings)

    # Per-IP rate limit
    await svc.rate_limiter.enforce(
        scope="jobs_ip",
        identifier=client_ip,
        limit=settings.rate_limit_jobs_per_minute,
        window_seconds=60,
        message="Download rate limit reached for your IP.",
    )

    # Validate URL & resolve short links safely
    resolved_url = await validate_and_resolve_url(body.url, follow_short_links=True)
    platform = detect_platform(resolved_url)
    normalized = normalize_url(resolved_url, platform)

    # Idempotency check: same (url, format, options) in-flight or still ready -> return same job
    idem_key = make_idempotency_key(
        normalized_url=normalized,
        preset=body.preset.value if body.preset else None,
        format_id=body.format_id,
        audio_format=body.audio_format,
        subtitle_lang=body.subtitle_lang,
        download_thumbnail=body.download_thumbnail,
        playlist_item=body.playlist_item,
    )
    existing = await svc.job_store.find_idempotent_job(idem_key)
    if existing is not None:
        if existing.status == JobStatus.READY:
            meta = await svc.job_store.get_artifact_metadata(existing.job_id)
            media_path = (meta or {}).get("media", {}).get("path") if isinstance(meta, dict) else None
            file_exists = bool(media_path and await asyncio.to_thread(os.path.isfile, str(media_path)))
            if not file_exists:
                await svc.job_store.clear_idempotent_job(idem_key)
                existing = None
            else:
                fresh_token = create_download_token(
                    job_id=existing.job_id,
                    kind="media",
                    secret=settings.hmac_secret.get_secret_value(),
                    ttl_seconds=settings.download_token_ttl_seconds,
                )
                existing.download_token = fresh_token
                existing.download_url = f"/api/v1/files/{fresh_token}"
                await svc.job_store.save_job(existing, publish=False)
        if existing is not None:
            return CreateJobResponse(job_id=existing.job_id, status=existing.status, reused=True)

    # Per-IP concurrent active jobs cap
    active_count = await svc.rate_limiter.count_active_ip_jobs(client_ip)
    if active_count >= settings.max_concurrent_jobs_per_ip:
        raise AppError(
            code=ErrorCode.RATE_LIMITED,
            message=f"You already have {active_count} active downloads in progress.",
            hint="Wait for one of your current downloads to finish or cancel it.",
            retryable=True,
            status_code=429,
        )

    # Disk-quota guard before enqueuing
    svc.storage.assert_disk_quota()

    # Pre-populate title/thumbnail from resolve cache if available
    cached_meta = await svc.job_store.get_cached_resolve(normalized)
    job_id = uuid.uuid4().hex
    now = time.time()

    snapshot = JobSnapshot(
        job_id=job_id,
        platform=platform,
        url=normalized,
        title=cached_meta.title if cached_meta else None,
        thumbnail_url=cached_meta.thumbnail_url if cached_meta else None,
        status=JobStatus.QUEUED,
        progress_percent=0.0,
        phase_detail="Queued for download...",
        created_at=now,
        updated_at=now,
    )

    await svc.job_store.save_job(snapshot, publish=False)
    await svc.job_store.bind_idempotent_job(idem_key, job_id)
    await svc.rate_limiter.register_ip_job(client_ip, job_id, ttl_seconds=settings.job_timeout_seconds)

    # Enqueue onto arq worker pool (or injected test dispatcher)
    await svc.enqueue_job(
        job_id=job_id,
        normalized_url=normalized,
        platform_str=platform.value,
        preset_str=body.preset.value if body.preset else None,
        format_id=body.format_id,
        audio_format=body.audio_format,
        subtitle_lang=body.subtitle_lang,
        download_thumbnail=body.download_thumbnail,
        playlist_item=body.playlist_item,
        client_ip=client_ip,
        idem_key=idem_key,
    )

    try:
        depth = await svc.redis.zcard("arq:queue")
        QUEUE_DEPTH.set(int(depth or 0))
    except Exception as exc:
        logger.debug("Queue depth metric update skipped: %s", exc)

    return CreateJobResponse(job_id=job_id, status=JobStatus.QUEUED, reused=False)


@router.get("/jobs/{job_id}", response_model=JobSnapshot)
async def get_job_status(job_id: str, request: Request) -> JobSnapshot:
    svc = get_app_state(request)
    snapshot: JobSnapshot | None = await svc.job_store.get_job(job_id)
    if snapshot is None:
        raise AppError(
            code=ErrorCode.JOB_NOT_FOUND,
            message="Download job not found or expired.",
            hint="Start a new download from the main page.",
            status_code=404,
        )
    return snapshot


@router.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str, request: Request) -> StreamingResponse:
    """Server-Sent Events stream of live job progress snapshots."""
    svc = get_app_state(request)
    initial = await svc.job_store.get_job(job_id)
    if initial is None:
        raise AppError(
            code=ErrorCode.JOB_NOT_FOUND,
            message="Download job not found or expired.",
            hint="Start a new download from the main page.",
            status_code=404,
        )

    async def event_generator() -> AsyncIterator[str]:
        # Always send current state immediately upon connection/reconnect
        yield f"event: progress\ndata: {initial.model_dump_json()}\n\n"
        if initial.status in _TERMINAL_STATES:
            return

        pubsub = svc.redis.pubsub()
        channel = svc.job_store.event_channel(job_id)
        await pubsub.subscribe(channel)
        try:
            last_ping = time.monotonic()
            while True:
                if await request.is_disconnected():
                    break

                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    raw_data = msg["data"]
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")
                    yield f"event: progress\ndata: {raw_data}\n\n"
                    try:
                        snap = JobSnapshot.model_validate_json(raw_data)
                        if snap.status in _TERMINAL_STATES:
                            return
                    except Exception as exc:
                        logger.debug("Ignored malformed SSE event payload: %s", exc)
                else:
                    # Periodic heartbeat + state re-check in case a pubsub event was missed during reconnect
                    now_m = time.monotonic()
                    if now_m - last_ping >= 10.0:
                        last_ping = now_m
                        latest = await svc.job_store.get_job(job_id)
                        if latest is not None:
                            yield f"event: progress\ndata: {latest.model_dump_json()}\n\n"
                            if latest.status in _TERMINAL_STATES:
                                return
                        else:
                            return
                        yield ": keepalive\n\n"
                await asyncio.sleep(0.05)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str, request: Request) -> dict[str, str]:
    """Cancel an active job or clean up an already completed job's temporary files."""
    svc = get_app_state(request)
    snapshot = await svc.job_store.get_job(job_id)
    if snapshot is None:
        raise AppError(
            code=ErrorCode.JOB_NOT_FOUND,
            message="Download job not found.",
            hint="It may have already expired.",
            status_code=404,
        )

    await svc.job_store.request_cancel(job_id)
    snapshot.status = JobStatus.CANCELLED
    snapshot.phase_detail = "Cancelled and cleaned up"
    await svc.job_store.save_job(snapshot, publish=True)
    svc.storage.cleanup_job(job_id)
    await svc.job_store.delete_artifact_metadata(job_id)
    return {"status": "cancelled", "job_id": job_id}
