"""Application configuration using Pydantic Settings v2."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core app
    app_name: str = "FastDL"
    app_version: str = "1.0.0"
    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_request_body_bytes: int = 65_536  # 64 KiB for JSON API payloads

    # Security & Signing
    hmac_secret: SecretStr = Field(default=SecretStr("dev-insecure-change-me-in-production-32bytes-min"))
    download_token_ttl_seconds: int = 900  # 15 min
    trust_proxy_headers: bool = True

    # Cloudflare Turnstile (optional)
    turnstile_enabled: bool = False
    turnstile_secret_key: SecretStr = Field(default=SecretStr(""))
    turnstile_site_key: str = ""

    # Redis & Worker
    redis_url: str = "redis://redis:6379/0"
    worker_concurrency: int = 3
    per_platform_concurrency: int = 2
    job_timeout_seconds: int = 1800
    resolve_cache_ttl_seconds: int = 720  # 12 min
    file_ttl_seconds: int = 1800  # 30 min
    max_playlist_items: int = 15

    # Storage & Limits
    storage_dir: Path = Path("/var/lib/vdl/downloads")
    tmp_dir: Path = Path("/tmp/vdl")
    min_free_disk_bytes: int = 1_073_741_824  # 1 GiB
    max_duration_seconds: int = 7200  # 2 hours
    max_filesize_bytes: int = 2_147_483_648  # 2 GiB
    progressive_direct_stream: bool = True

    # Rate limits (per-IP & per-platform)
    rate_limit_enabled: bool = True
    rate_limit_resolve_per_minute: int = 30
    rate_limit_jobs_per_minute: int = 15
    max_concurrent_jobs_per_ip: int = 3
    platform_rate_limit_per_minute: int = 60

    # Speed tuning
    ytdlp_concurrent_fragments: int = 12
    ytdlp_http_chunk_size: int = 10_485_760  # 10 MiB
    ytdlp_retries: int = 5
    ytdlp_fragment_retries: int = 5
    ytdlp_buffer_size: int = 65_536
    ytdlp_socket_timeout: int = 20
    ytdlp_force_ipv4: bool = True
    enable_aria2c: bool = False
    aria2c_connections: int = 16
    aria2c_splits: int = 16
    aria2c_min_split_size: str = "1M"

    # Anti-block L1: yt-dlp auto-update
    ytdlp_auto_update: bool = True
    ytdlp_channel: Literal["stable", "nightly"] = "stable"
    ytdlp_pinned_version: str = ""
    ytdlp_overlay_dir: Path = Path("/var/lib/vdl/ytdlp-overlay")

    # Anti-block L2: Browser impersonation (curl_cffi)
    impersonate_enabled: bool = True
    impersonate_target: str = "chrome"

    # Anti-block L3: YouTube PO Token & player clients
    pot_provider_url: str = "http://pot-provider:4416"
    pot_provider_enabled: bool = True
    youtube_player_clients: str = "default,mweb,android_vr,web_safari,ios,web_embedded,tv"

    # Anti-block L4: Cookies
    cookies_dir: Path = Path("/run/secrets/cookies")

    # Anti-block L5: Egress Proxies
    proxy_urls: str = ""
    proxy_urls_youtube: str = ""
    proxy_urls_x: str = ""
    proxy_urls_instagram: str = ""
    proxy_urls_facebook: str = ""
    proxy_strategy: Literal["round_robin", "sticky"] = "sticky"
    proxy_cooldown_seconds: int = 300
    proxy_max_failures: int = 3

    # Anti-block L6: Circuit breaker
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown_seconds: int = 120
    jitter_min_ms: int = 50
    jitter_max_ms: int = 250

    # Anti-block L7: Canary URLs (optional overrides)
    canary_enabled: bool = True
    canary_url_youtube: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    canary_url_x: str = "https://x.com/captainamerica/status/719944021058060289"
    canary_url_instagram: str = "https://www.instagram.com/reel/Chunk8-jurw/"
    canary_url_facebook: str = "https://www.facebook.com/watch/?v=10153231379946729"

    # Observability (L8)
    sentry_dsn: str = ""
    metrics_enabled: bool = True

    @field_validator("ytdlp_concurrent_fragments")
    @classmethod
    def _clamp_fragments(cls, v: int) -> int:
        return max(1, min(32, v))

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def youtube_client_list(self) -> list[str]:
        return [c.strip() for c in self.youtube_player_clients.split(",") if c.strip()]

    def platform_proxy_list(self, platform: str) -> list[str]:
        specific = getattr(self, f"proxy_urls_{platform}", "")
        raw = specific if specific else self.proxy_urls
        return [p.strip() for p in raw.split(",") if p.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
