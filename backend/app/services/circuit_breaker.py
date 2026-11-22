"""Anti-Block L6: Per-(platform, proxy) Redis circuit breaker and jittered backoff."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

from app.errors import AppError, ErrorCode
from app.schemas import Platform

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Redis-backed circuit breaker scoped per (platform, proxy_label).
    Opens after `threshold` consecutive anti-bot/429/403 signals and pauses traffic
    for `cooldown_seconds`, surfacing a friendly 'try again in N seconds' message.
    """

    def __init__(
        self,
        redis_client: Any,
        *,
        threshold: int = 5,
        cooldown_seconds: int = 120,
    ) -> None:
        self._redis = redis_client
        self._threshold = max(1, threshold)
        self._cooldown_seconds = max(10, cooldown_seconds)

    @staticmethod
    def _fail_key(platform: Platform, proxy_label: str) -> str:
        return f"vdl:cb:fail:{platform.value}:{proxy_label}"

    @staticmethod
    def _open_key(platform: Platform, proxy_label: str) -> str:
        return f"vdl:cb:open:{platform.value}:{proxy_label}"

    async def remaining_cooldown(self, platform: Platform, proxy_label: str = "direct") -> int:
        raw = await self._redis.get(self._open_key(platform, proxy_label))
        if not raw:
            return 0
        until = float(raw)
        rem = int(until - time.time())
        return max(0, rem)

    async def assert_closed(self, platform: Platform, proxy_label: str = "direct") -> None:
        rem = await self.remaining_cooldown(platform, proxy_label)
        if rem > 0:
            raise AppError(
                code=ErrorCode.CIRCUIT_OPEN,
                message=f"{platform.value.title()} is temporarily paused due to upstream rate limits.",
                hint=f"Please try again in {rem} seconds.",
                retryable=True,
                status_code=503,
            )

    async def record_success(self, platform: Platform, proxy_label: str = "direct") -> None:
        await self._redis.delete(
            self._fail_key(platform, proxy_label),
            self._open_key(platform, proxy_label),
        )

    async def record_failure(self, platform: Platform, proxy_label: str = "direct") -> bool:
        """Increment consecutive failures; returns True if circuit just tripped open."""
        fkey = self._fail_key(platform, proxy_label)
        count = int(await self._redis.incr(fkey))
        await self._redis.expire(fkey, self._cooldown_seconds * 2)

        if count >= self._threshold:
            until = time.time() + self._cooldown_seconds
            await self._redis.set(
                self._open_key(platform, proxy_label),
                f"{until:.3f}",
                ex=self._cooldown_seconds,
            )
            await self._redis.delete(fkey)
            logger.warning(
                "Circuit breaker tripped OPEN for platform=%s proxy=%s cooldown=%ds",
                platform.value,
                proxy_label,
                self._cooldown_seconds,
                extra={"platform": platform.value, "proxy": proxy_label},
            )
            return True
        return False


async def jitter_sleep(min_ms: int = 50, max_ms: int = 250) -> None:
    if max_ms <= 0:
        return
    delay = random.uniform(max(0, min_ms), max(min_ms, max_ms)) / 1000.0  # noqa: S311
    await asyncio.sleep(delay)


async def backoff_sleep(attempt: int, base_seconds: float = 0.6, max_seconds: float = 8.0) -> None:
    exp = min(max_seconds, base_seconds * (2 ** max(0, attempt)))
    jitter = random.uniform(0.0, exp * 0.35)  # noqa: S311
    await asyncio.sleep(exp + jitter)
