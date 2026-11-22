"""FastAPI application factory, lifespan wiring, middleware, exception handlers, and /metrics."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis

from app.api import files, health, jobs, resolve
from app.config import Settings, get_settings
from app.errors import AppError, ErrorCode
from app.logging_setup import request_id_ctx, setup_logging
from app.schemas import ErrorDetail, ErrorResponse
from app.security.ratelimit import RateLimiter
from app.services.circuit_breaker import CircuitBreaker
from app.services.cookies import CookieManager
from app.services.extractor import MediaExtractor
from app.services.job_store import JobStore
from app.services.proxies import ProxyPool
from app.services.storage import StorageManager

logger = logging.getLogger(__name__)


@dataclass
class AppServices:
    settings: Settings
    redis: Any
    arq_pool: ArqRedis | None
    cookies: CookieManager
    proxies: ProxyPool
    circuit_breaker: CircuitBreaker
    extractor: MediaExtractor
    storage: StorageManager
    job_store: JobStore
    rate_limiter: RateLimiter
    enqueue_override: Callable[..., Any] | None = None

    async def enqueue_job(self, **kwargs: Any) -> Any:
        if self.enqueue_override is not None:
            return await self.enqueue_override(**kwargs)
        if self.arq_pool is None:
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Background job queue is unavailable.",
                hint="Please retry in a moment.",
                retryable=True,
                status_code=503,
            )
        return await self.arq_pool.enqueue_job(
            "download_job_task",
            _job_id=kwargs["job_id"],
            **kwargs,
        )


def create_app(
    *,
    settings: Settings | None = None,
    services_override: AppServices | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    setup_logging(cfg.log_level)

    if cfg.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=cfg.sentry_dsn, traces_sample_rate=0.1)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if services_override is not None:
            app.state.services = services_override
            yield
            return

        redis_client = Redis.from_url(cfg.redis_url, decode_responses=True)
        arq_pool: ArqRedis | None = None
        try:
            arq_pool = await create_pool(RedisSettings.from_dsn(cfg.redis_url))
        except Exception as exc:
            logger.warning("Could not initialize arq pool on startup: %s", exc)

        cookies = CookieManager(cfg.cookies_dir)
        proxies = ProxyPool.from_settings(cfg)
        cb = CircuitBreaker(
            redis_client,
            threshold=cfg.circuit_breaker_threshold,
            cooldown_seconds=cfg.circuit_breaker_cooldown_seconds,
        )
        extractor = MediaExtractor(cfg, cookies, proxies, cb)
        storage = StorageManager(
            cfg.storage_dir,
            cfg.tmp_dir,
            min_free_disk_bytes=cfg.min_free_disk_bytes,
            file_ttl_seconds=cfg.file_ttl_seconds,
        )
        job_store = JobStore(redis_client, file_ttl_seconds=cfg.file_ttl_seconds)
        rate_limiter = RateLimiter(redis_client, enabled=cfg.rate_limit_enabled)

        app.state.services = AppServices(
            settings=cfg,
            redis=redis_client,
            arq_pool=arq_pool,
            cookies=cookies,
            proxies=proxies,
            circuit_breaker=cb,
            extractor=extractor,
            storage=storage,
            job_store=job_store,
            rate_limiter=rate_limiter,
        )
        logger.info("FastDL API started env=%s version=%s", cfg.app_env, cfg.app_version)
        try:
            yield
        finally:
            if arq_pool is not None:
                await arq_pool.aclose()
            await redis_client.aclose()
            logger.info("FastDL API shut down cleanly")

    app = FastAPI(
        title="FastDL Video Downloader API",
        version=cfg.app_version,
        description="Production-grade public video downloader API for YouTube, X, Instagram, and Facebook.",
        docs_url="/api/docs" if cfg.app_env != "production" else None,
        redoc_url="/api/redoc" if cfg.app_env != "production" else None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID", "Range"],
        expose_headers=["Content-Disposition", "Content-Range", "Accept-Ranges", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context_and_security_middleware(
        request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_ctx.set(req_id)
        t0 = time.perf_counter()

        # Enforce request body size cap on write endpoints
        content_len = request.headers.get("content-length")
        if content_len and content_len.isdigit() and int(content_len) > cfg.max_request_body_bytes:
            request_id_ctx.reset(token)
            return JSONResponse(
                status_code=413,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code="PAYLOAD_TOO_LARGE",
                        message="Request body is too large.",
                        hint="Submit a valid URL payload only.",
                        retryable=False,
                    )
                ).model_dump(),
            )

        try:
            response: Response = await call_next(request)
        finally:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if not request.url.path.startswith(("/healthz", "/metrics")):
                logger.info(
                    "HTTP %s %s",
                    request.method,
                    request.url.path,
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": duration_ms,
                    },
                )
            request_id_ctx.reset(token)

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_response().model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        first_msg = exc.errors()[0].get("msg", "Invalid request payload") if exc.errors() else "Invalid request"
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INVALID_URL.value,
                    message=str(first_msg),
                    hint="Check the request fields and ensure the URL is valid.",
                    retryable=False,
                )
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="HTTP_ERROR",
                    message=str(exc.detail),
                    hint="Check the request and try again.",
                    retryable=exc.status_code >= 500,
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR.value,
                    message="An unexpected server error occurred.",
                    hint="Please try again shortly.",
                    retryable=True,
                )
            ).model_dump(),
        )

    app.include_router(health.router)
    app.include_router(resolve.router)
    app.include_router(jobs.router)
    app.include_router(files.router)

    if cfg.metrics_enabled:

        @app.get("/metrics", include_in_schema=False)
        async def prometheus_metrics() -> Response:
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
