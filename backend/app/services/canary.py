"""Anti-Block L7: Daily canary job resolving one public URL per platform -> Prometheus & alerts."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import Settings
from app.errors import AppError
from app.metrics import CANARY_LATENCY, CANARY_STATUS
from app.schemas import Platform
from app.services.extractor import MediaExtractor
from app.services.platforms import normalize_url

logger = logging.getLogger(__name__)


async def run_canary_checks(
    settings: Settings,
    extractor: MediaExtractor,
) -> dict[str, dict[str, Any]]:
    """Resolve one known-good public URL per platform and export Prometheus health gauges."""
    targets: dict[Platform, str] = {
        Platform.YOUTUBE: settings.canary_url_youtube,
        Platform.X: settings.canary_url_x,
        Platform.INSTAGRAM: settings.canary_url_instagram,
        Platform.FACEBOOK: settings.canary_url_facebook,
    }
    results: dict[str, dict[str, Any]] = {}

    for platform, url in targets.items():
        if not url:
            continue
        t0 = time.perf_counter()
        try:
            norm = normalize_url(url, platform)
            resolved = await extractor.resolve(url=url, normalized_url=norm, platform=platform)
            elapsed = time.perf_counter() - t0
            CANARY_STATUS.labels(platform=platform.value).set(1)
            CANARY_LATENCY.labels(platform=platform.value).set(elapsed)
            results[platform.value] = {
                "ok": True,
                "latency_s": round(elapsed, 2),
                "formats": len(resolved.formats),
                "title": resolved.title[:60],
            }
            logger.info(
                "Canary PASS platform=%s latency=%.2fs formats=%d",
                platform.value,
                elapsed,
                len(resolved.formats),
                extra={"platform": platform.value, "duration_ms": int(elapsed * 1000)},
            )
        except AppError as exc:
            elapsed = time.perf_counter() - t0
            CANARY_STATUS.labels(platform=platform.value).set(0)
            CANARY_LATENCY.labels(platform=platform.value).set(elapsed)
            results[platform.value] = {
                "ok": False,
                "latency_s": round(elapsed, 2),
                "error_code": exc.code.value,
                "message": exc.message,
            }
            logger.error(
                "CANARY ALERT: platform=%s DEGRADED code=%s msg=%s",
                platform.value,
                exc.code.value,
                exc.message,
                extra={"platform": platform.value, "error_code": exc.code.value},
            )
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            CANARY_STATUS.labels(platform=platform.value).set(0)
            CANARY_LATENCY.labels(platform=platform.value).set(elapsed)
            results[platform.value] = {
                "ok": False,
                "latency_s": round(elapsed, 2),
                "error_code": "UNEXPECTED",
                "message": str(exc),
            }
            logger.error(
                "CANARY ALERT: platform=%s unexpected failure: %s",
                platform.value,
                exc,
                extra={"platform": platform.value},
            )

    return results


async def _cli_main() -> int:
    import json
    import tempfile
    from pathlib import Path

    from redis.asyncio import Redis

    from app.config import get_settings
    from app.services.circuit_breaker import CircuitBreaker
    from app.services.cookies import CookieManager
    from app.services.proxies import ProxyPool

    settings = get_settings()
    settings.pot_provider_enabled = False
    settings.jitter_min_ms = 0
    settings.jitter_max_ms = 0

    try:
        import fakeredis.aioredis

        redis_client: Any = fakeredis.aioredis.FakeRedis(decode_responses=True)
    except ImportError:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

    with tempfile.TemporaryDirectory() as td:
        cookies = CookieManager(Path(td) / "cookies")
        proxies = ProxyPool.from_settings(settings)
        cb = CircuitBreaker(redis_client)
        extractor = MediaExtractor(settings, cookies, proxies, cb)
        res = await run_canary_checks(settings, extractor)
        print(json.dumps(res, indent=2))
    await redis_client.aclose()
    return 0


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(_cli_main()))
