"""Health, readiness, and version endpoints."""

from __future__ import annotations

from typing import Literal

import httpx
from fastapi import APIRouter, Request, Response

from app.api.deps import get_app_state
from app.schemas import ReadyResponse, VersionResponse
from app.services.extractor import is_aria2c_available, is_curl_cffi_available
from app.services.updater import current_ytdlp_version, ffmpeg_version

router = APIRouter(tags=["system"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/readyz", response_model=ReadyResponse)
async def readyz(request: Request, response: Response) -> ReadyResponse:
    """Readiness probe verifying Redis, ffmpeg, yt-dlp, disk quota, cookies, and optional PO token sidecar."""
    svc = get_app_state(request)
    settings = svc.settings

    redis_ok = False
    try:
        pong = await svc.redis.ping()
        redis_ok = bool(pong)
    except Exception:
        redis_ok = False

    ff_ver = ffmpeg_version()
    ffmpeg_ok = ff_ver != "unavailable"
    yt_ver = current_ytdlp_version()

    disk_free = svc.storage.free_bytes()
    disk_ok = svc.storage.has_sufficient_space()

    cookies_status = svc.cookies.status_summary()
    proxies_healthy = svc.proxies.healthy_count()

    pot_ok: bool | None = None
    if settings.pot_provider_enabled and settings.pot_provider_url:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{settings.pot_provider_url.rstrip('/')}/ping")
                pot_ok = r.status_code < 500
        except Exception:
            pot_ok = False

    core_ok = redis_ok and ffmpeg_ok and disk_ok
    any_cookie_expired = any(v == "expired" for v in cookies_status.values())
    status_val: Literal["ready", "degraded", "not_ready"] = "ready"
    if not core_ok:
        status_val = "not_ready"
        response.status_code = 503
    elif any_cookie_expired or pot_ok is False:
        status_val = "degraded"

    return ReadyResponse(
        status=status_val,
        redis=redis_ok,
        ffmpeg=ffmpeg_ok,
        ytdlp_version=yt_ver,
        pot_provider=pot_ok,
        disk_free_bytes=disk_free,
        disk_ok=disk_ok,
        cookies=cookies_status,
        proxies_healthy=proxies_healthy,
        details={
            "ffmpeg_version": ff_ver,
            "impersonate_enabled": settings.impersonate_enabled and is_curl_cffi_available(),
            "aria2c_available": is_aria2c_available(),
        },
    )


@router.get("/api/v1/version", response_model=VersionResponse)
async def version(request: Request) -> VersionResponse:
    """Expose application, yt-dlp, and ffmpeg versions and runtime capabilities."""
    svc = get_app_state(request)
    settings = svc.settings
    return VersionResponse(
        app_version=settings.app_version,
        ytdlp_version=current_ytdlp_version(),
        ffmpeg_version=ffmpeg_version(),
        aria2c_available=is_aria2c_available(),
        curl_cffi_available=is_curl_cffi_available(),
        pot_provider_enabled=settings.pot_provider_enabled,
    )
