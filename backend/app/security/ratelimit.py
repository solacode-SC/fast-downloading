"""Redis-backed token-bucket / sliding-window rate limiting and per-IP concurrency guard (L6)."""

from __future__ import annotations

import time
from typing import Any

from app.errors import AppError, ErrorCode


class RateLimiter:
    """Sliding-window rate limiter backed by Redis sorted sets."""

    def __init__(self, redis_client: Any, *, enabled: bool = True) -> None:
        self._redis = redis_client
        self._enabled = enabled

    async def check_limit(
        self,
        *,
        scope: str,
        identifier: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """
        Record a request and check whether it is within `limit` per `window_seconds`.
        Returns (allowed, retry_after_seconds).
        """
        if not self._enabled or limit <= 0:
            return True, 0

        now = time.time()
        window_start = now - window_seconds
        key = f"vdl:rl:{scope}:{identifier}"
        member = f"{now:.6f}"

        pipe = self._redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {member: now})
        pipe.expire(key, window_seconds + 5)
        results = await pipe.execute()

        current_count = int(results[1])
        if current_count >= limit:
            # Remove the optimistically added member so rejected hits don't compound
            await self._redis.zrem(key, member)
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            retry_after = max(1, int(window_seconds - (now - float(oldest[0][1])))) if oldest else window_seconds
            return False, retry_after

        return True, 0

    async def enforce(
        self,
        *,
        scope: str,
        identifier: str,
        limit: int,
        window_seconds: int = 60,
        message: str = "Too many requests. Please slow down.",
    ) -> None:
        allowed, retry_after = await self.check_limit(
            scope=scope,
            identifier=identifier,
            limit=limit,
            window_seconds=window_seconds,
        )
        if not allowed:
            raise AppError(
                code=ErrorCode.RATE_LIMITED,
                message=message,
                hint=f"Please wait {retry_after} seconds and try again.",
                retryable=True,
                status_code=429,
            )

    async def count_active_ip_jobs(self, client_ip: str) -> int:
        key = f"vdl:active_ip:{client_ip}"
        val = await self._redis.scard(key)
        return int(val or 0)

    async def register_ip_job(self, client_ip: str, job_id: str, ttl_seconds: int = 1800) -> None:
        key = f"vdl:active_ip:{client_ip}"
        pipe = self._redis.pipeline()
        pipe.sadd(key, job_id)
        pipe.expire(key, ttl_seconds)
        await pipe.execute()

    async def release_ip_job(self, client_ip: str, job_id: str) -> None:
        key = f"vdl:active_ip:{client_ip}"
        await self._redis.srem(key, job_id)
