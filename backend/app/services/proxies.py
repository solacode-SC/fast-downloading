"""Anti-Block L5: Egress Proxy Pool with per-platform assignment, health checks, ejection & cooldown."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.schemas import Platform

logger = logging.getLogger(__name__)


@dataclass
class ProxyEntry:
    url: str
    label: str
    failures: int = 0
    cooldown_until: float = 0.0
    last_ok: float = 0.0

    def is_available(self, now: float | None = None) -> bool:
        t = now if now is not None else time.time()
        return t >= self.cooldown_until


def mask_proxy_label(proxy_url: str) -> str:
    """Return a safe, credential-free label for logging and Prometheus metrics."""
    parsed = urlparse(proxy_url)
    host = parsed.hostname or "unknown"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}"


class ProxyPool:
    """
    Manages egress proxies per platform:
    - Supports http, https, socks5, socks5h URLs.
    - Supports round_robin or sticky-per-job selection.
    - Automatically ejects failing proxies for `cooldown_seconds` after `max_failures`,
      then automatically re-admits them after cooldown expires.
    """

    def __init__(
        self,
        *,
        platform_proxies: dict[Platform, list[str]],
        strategy: str = "sticky",
        max_failures: int = 3,
        cooldown_seconds: int = 300,
    ) -> None:
        self._strategy = strategy
        self._max_failures = max(1, max_failures)
        self._cooldown_seconds = max(10, cooldown_seconds)
        self._pools: dict[Platform, list[ProxyEntry]] = {}
        self._rr_index: dict[Platform, int] = {p: 0 for p in Platform}

        for platform in Platform:
            urls = platform_proxies.get(platform, [])
            self._pools[platform] = [ProxyEntry(url=u, label=mask_proxy_label(u)) for u in urls if u.strip()]

    @classmethod
    def from_settings(cls, settings: Settings) -> ProxyPool:
        mapping = {p: settings.platform_proxy_list(p.value) for p in Platform}
        return cls(
            platform_proxies=mapping,
            strategy=settings.proxy_strategy,
            max_failures=settings.proxy_max_failures,
            cooldown_seconds=settings.proxy_cooldown_seconds,
        )

    def has_proxies(self, platform: Platform) -> bool:
        return bool(self._pools.get(platform))

    def healthy_count(self, platform: Platform | None = None, now: float | None = None) -> int:
        t = now if now is not None else time.time()
        if platform is not None:
            return sum(1 for entry in self._pools.get(platform, []) if entry.is_available(t))
        seen: set[str] = set()
        for entries in self._pools.values():
            for e in entries:
                if e.is_available(t):
                    seen.add(e.label)
        return len(seen)

    def select(
        self,
        platform: Platform,
        *,
        sticky_key: str | None = None,
        exclude: set[str] | None = None,
        now: float | None = None,
    ) -> ProxyEntry | None:
        """Select a healthy proxy for the platform, or None for direct connection."""
        t = now if now is not None else time.time()
        entries = self._pools.get(platform, [])
        if not entries:
            return None

        excluded = exclude or set()
        available = [e for e in entries if e.is_available(t) and e.url not in excluded]
        if not available:
            return None

        if self._strategy == "sticky" and sticky_key:
            digest = hashlib.sha256(sticky_key.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % len(available)
            return available[idx]

        idx = self._rr_index[platform] % len(available)
        self._rr_index[platform] = (self._rr_index[platform] + 1) % len(available)
        return available[idx]

    def record_success(self, platform: Platform, proxy_url: str, now: float | None = None) -> None:
        t = now if now is not None else time.time()
        for entry in self._pools.get(platform, []):
            if entry.url == proxy_url:
                entry.failures = 0
                entry.cooldown_until = 0.0
                entry.last_ok = t
                break

    def record_failure(self, platform: Platform, proxy_url: str, now: float | None = None) -> None:
        t = now if now is not None else time.time()
        for entry in self._pools.get(platform, []):
            if entry.url == proxy_url:
                entry.failures += 1
                if entry.failures >= self._max_failures:
                    entry.cooldown_until = t + self._cooldown_seconds
                    entry.failures = 0
                    logger.warning(
                        "Ejected proxy %s for %ds cooldown",
                        entry.label,
                        self._cooldown_seconds,
                        extra={"platform": platform.value, "proxy": entry.label},
                    )
                break

    async def health_check_all(self, test_url: str = "https://www.google.com/generate_204") -> dict[str, bool]:
        """Probe every configured unique proxy and eject unhealthy ones."""
        results: dict[str, bool] = {}
        seen: dict[str, list[Platform]] = {}
        for p, entries in self._pools.items():
            for e in entries:
                seen.setdefault(e.url, []).append(p)

        for proxy_url, platforms in seen.items():
            label = mask_proxy_label(proxy_url)
            ok = False
            try:
                async with httpx.AsyncClient(proxy=proxy_url, timeout=6.0) as client:
                    resp = await client.get(test_url)
                    ok = resp.status_code < 500
            except Exception:
                ok = False

            results[label] = ok
            for p in platforms:
                if ok:
                    self.record_success(p, proxy_url)
                else:
                    self.record_failure(p, proxy_url)
        return results
