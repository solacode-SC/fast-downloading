"""arq worker entrypoint and WorkerSettings configuration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.config import get_settings
from app.logging_setup import setup_logging
from app.schemas import Platform
from app.security.ratelimit import RateLimiter
from app.services.circuit_breaker import CircuitBreaker
from app.services.cookies import CookieManager
from app.services.extractor import MediaExtractor
from app.services.job_store import JobStore
from app.services.proxies import ProxyPool
from app.services.storage import StorageManager
from app.services.updater import update_ytdlp_with_rollback
from app.workers.tasks import (
    cleanup_expired_files_cron,
    daily_canary_check_cron,
    daily_ytdlp_update_cron,
    download_job_task,
)

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

    # Optional L1 startup yt-dlp update check (non-blocking fail-safe)
    if settings.ytdlp_auto_update and settings.app_env == "production":
        try:
            await asyncio.to_thread(update_ytdlp_with_rollback, settings)
        except Exception as exc:
            logger.warning("Startup yt-dlp update check failed (continuing): %s", exc)

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    cookie_manager = CookieManager(settings.cookies_dir)
    proxy_pool = ProxyPool.from_settings(settings)
    circuit_breaker = CircuitBreaker(
        redis_client,
        threshold=settings.circuit_breaker_threshold,
        cooldown_seconds=settings.circuit_breaker_cooldown_seconds,
    )
    extractor = MediaExtractor(settings, cookie_manager, proxy_pool, circuit_breaker)
    storage = StorageManager(
        settings.storage_dir,
        settings.tmp_dir,
        min_free_disk_bytes=settings.min_free_disk_bytes,
        file_ttl_seconds=settings.file_ttl_seconds,
    )
    job_store = JobStore(redis_client, file_ttl_seconds=settings.file_ttl_seconds)
    rate_limiter = RateLimiter(redis_client, enabled=settings.rate_limit_enabled)

    ctx["settings"] = settings
    ctx["redis_client"] = redis_client
    ctx["cookie_manager"] = cookie_manager
    ctx["proxy_pool"] = proxy_pool
    ctx["circuit_breaker"] = circuit_breaker
    ctx["extractor"] = extractor
    ctx["storage"] = storage
    ctx["job_store"] = job_store
    ctx["rate_limiter"] = rate_limiter
    ctx["platform_semaphores"] = {p: asyncio.Semaphore(settings.per_platform_concurrency) for p in Platform}
    logger.info(
        "Worker started concurrency=%d per_platform=%d",
        settings.worker_concurrency,
        settings.per_platform_concurrency,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    redis_client: Redis | None = ctx.get("redis_client")
    if redis_client is not None:
        await redis_client.aclose()
    logger.info("Worker shut down cleanly")


def _build_redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.redis_url)


class WorkerSettings:
    functions = [download_job_task]
    cron_jobs = [
        cron(cleanup_expired_files_cron, minute={0, 10, 20, 30, 40, 50}),
        cron(daily_ytdlp_update_cron, hour=3, minute=15),
        cron(daily_canary_check_cron, hour=4, minute=0),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _build_redis_settings()
    max_jobs = get_settings().worker_concurrency
    job_timeout = get_settings().job_timeout_seconds
    keep_result = 600
    health_check_interval = 30
