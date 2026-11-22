"""Shared pytest fixtures for backend unit and integration tests."""

from __future__ import annotations

from pathlib import Path

import fakeredis.aioredis
import pytest
from app.config import Settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        redis_url="redis://localhost:6379/15",
        storage_dir=tmp_path / "downloads",
        tmp_dir=tmp_path / "tmp",
        cookies_dir=tmp_path / "cookies",
        ytdlp_overlay_dir=tmp_path / "overlay",
        min_free_disk_bytes=1024,
        rate_limit_enabled=True,
        rate_limit_resolve_per_minute=20,
        rate_limit_jobs_per_minute=10,
        max_concurrent_jobs_per_ip=3,
        pot_provider_enabled=False,
        ytdlp_auto_update=False,
        jitter_min_ms=0,
        jitter_max_ms=0,
    )


@pytest.fixture
async def fake_redis() -> fakeredis.aioredis.FakeRedis:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()
