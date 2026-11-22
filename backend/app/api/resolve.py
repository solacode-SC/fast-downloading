"""POST /api/v1/resolve: URL validation, SSRF protection, platform detection, cached metadata & formats."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app.api.deps import get_app_state, get_client_ip
from app.metrics import RESOLVE_DURATION, RESOLVE_REQUESTS
from app.schemas import ResolveRequest, ResolveResponse
from app.security.ssrf import validate_and_resolve_url
from app.services.platforms import detect_platform, normalize_url

router = APIRouter(prefix="/api/v1", tags=["resolve"])


@router.post("/resolve", response_model=ResolveResponse)
async def resolve_media(body: ResolveRequest, request: Request) -> ResolveResponse:
    svc = get_app_state(request)
    settings = svc.settings
    client_ip = get_client_ip(request, settings)

    await svc.rate_limiter.enforce(
        scope="resolve_ip",
        identifier=client_ip,
        limit=settings.rate_limit_resolve_per_minute,
        window_seconds=60,
        message="Too many resolve requests from your IP.",
    )

    started = time.perf_counter()
    resolved_url = await validate_and_resolve_url(body.url, follow_short_links=True)
    platform = detect_platform(resolved_url)
    normalized = normalize_url(resolved_url, platform)

    # Check Redis cache first (10-15 min TTL minimizes upstream platform hits)
    cached: ResolveResponse | None = await svc.job_store.get_cached_resolve(normalized)
    if cached is not None:
        cached.resolve_ms = int((time.perf_counter() - started) * 1000)
        RESOLVE_REQUESTS.labels(platform=platform.value, status="ok", cached="true").inc()
        return cached

    # Per-platform rate limit (polite traffic shaping L6)
    await svc.rate_limiter.enforce(
        scope="resolve_platform",
        identifier=platform.value,
        limit=settings.platform_rate_limit_per_minute,
        window_seconds=60,
        message=f"High traffic to {platform.value.title()}. Please retry shortly.",
    )

    try:
        result: ResolveResponse = await svc.extractor.resolve(
            url=body.url.strip(),
            normalized_url=normalized,
            platform=platform,
        )
    except Exception:
        RESOLVE_REQUESTS.labels(platform=platform.value, status="error", cached="false").inc()
        raise

    elapsed = time.perf_counter() - started
    RESOLVE_REQUESTS.labels(platform=platform.value, status="ok", cached="false").inc()
    RESOLVE_DURATION.labels(platform=platform.value).observe(elapsed)

    await svc.job_store.set_cached_resolve(normalized, result, ttl_seconds=settings.resolve_cache_ttl_seconds)
    return result
