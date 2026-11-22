"""Integration tests: FastAPI + Redis + arq worker task with mocked extractor."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.config import Settings
from app.main import AppServices, create_app
from app.schemas import FormatItem, Platform, Preset, PresetOption, ResolveResponse
from app.security.ratelimit import RateLimiter
from app.services.circuit_breaker import CircuitBreaker
from app.services.cookies import CookieManager
from app.services.extractor import DownloadArtifact, MediaExtractor
from app.services.job_store import JobStore
from app.services.proxies import ProxyPool
from app.services.storage import StorageManager
from app.workers.tasks import download_job_task


class MockExtractor(MediaExtractor):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.resolve_calls = 0
        self.download_calls = 0

    async def resolve(
        self,
        *,
        url: str,
        normalized_url: str,
        platform: Platform,
    ) -> ResolveResponse:
        self.resolve_calls += 1
        return ResolveResponse(
            url=url,
            normalized_url=normalized_url,
            platform=platform,
            id="mock123",
            title="Test Video Café",
            uploader="TestChannel",
            duration_seconds=45,
            thumbnail_url="https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg",
            presets=[
                PresetOption(
                    id=Preset.BEST,
                    label="Best Available",
                    description="Highest quality",
                    estimated_ext="mp4",
                    estimated_height=1080,
                    estimated_size_bytes=1024,
                )
            ],
            formats=[
                FormatItem(
                    format_id="137",
                    ext="mp4",
                    resolution="1080p",
                    width=1920,
                    height=1080,
                    fps=30.0,
                    vcodec="avc1",
                    acodec="aac",
                    is_progressive=True,
                    compatible=True,
                    filesize_bytes=1024,
                )
            ],
            subtitles=[],
            cached=False,
            resolve_ms=12,
        )

    async def download(
        self,
        *,
        job_id: str,
        normalized_url: str,
        platform: Platform,
        preset: Preset | None,
        format_id: str | None,
        audio_format: str | None,
        subtitle_lang: str | None,
        download_thumbnail: bool,
        playlist_item: int | None,
        work_dir: Path,
        on_progress: Any,
        is_cancelled: Any,
    ) -> DownloadArtifact:
        self.download_calls += 1
        on_progress(
            {
                "status": "downloading",
                "downloaded_bytes": 512,
                "total_bytes": 1024,
                "speed": 2048.0,
                "eta": 1,
            }
        )
        media_file = work_dir / "media.mp4"
        content = b"0123456789ABCDEF" * 64  # 1024 bytes deterministic payload
        media_file.write_bytes(content)
        return DownloadArtifact(
            media_path=media_file,
            filename="Test Video Café.mp4",
            ext="mp4",
            title="Test Video Café",
            filesize_bytes=len(content),
        )


@pytest.mark.asyncio
async def test_full_job_lifecycle_range_idempotency_cancel_ratelimit(
    test_settings: Settings,
    fake_redis: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Stub DNS so tests run fully offline without hitting external DNS
    monkeypatch.setattr("app.security.ssrf._resolve_host_sync", lambda _h: ["142.250.190.46"])

    cookies = CookieManager(test_settings.cookies_dir)
    proxies = ProxyPool.from_settings(test_settings)
    cb = CircuitBreaker(fake_redis)
    extractor = MockExtractor(test_settings, cookies, proxies, cb)
    storage = StorageManager(
        test_settings.storage_dir,
        test_settings.tmp_dir,
        min_free_disk_bytes=1024,
        file_ttl_seconds=1800,
    )
    job_store = JobStore(fake_redis, file_ttl_seconds=1800)
    rate_limiter = RateLimiter(fake_redis, enabled=True)

    worker_ctx: dict[str, Any] = {
        "settings": test_settings,
        "redis_client": fake_redis,
        "extractor": extractor,
        "storage": storage,
        "job_store": job_store,
        "rate_limiter": rate_limiter,
        "platform_semaphores": {p: asyncio.Semaphore(2) for p in Platform},
    }

    queued_tasks: list[asyncio.Task[Any]] = []

    async def inline_enqueue(**kwargs: Any) -> None:
        queued_tasks.append(asyncio.create_task(download_job_task(worker_ctx, **kwargs)))

    services = AppServices(
        settings=test_settings,
        redis=fake_redis,
        arq_pool=None,
        cookies=cookies,
        proxies=proxies,
        circuit_breaker=cb,
        extractor=extractor,
        storage=storage,
        job_store=job_store,
        rate_limiter=rate_limiter,
        enqueue_override=inline_enqueue,
    )
    app = create_app(settings=test_settings, services_override=services)

    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        # 1. Health, version, metrics
        r_health = await client.get("/healthz")
        assert r_health.status_code == 200
        assert r_health.json() == {"status": "ok"}

        r_ver = await client.get("/api/v1/version")
        assert r_ver.status_code == 200
        assert "ytdlp_version" in r_ver.json()

        r_metrics = await client.get("/metrics")
        assert r_metrics.status_code == 200
        assert "vdl_resolve_requests_total" in r_metrics.text

        # 2. SSRF rejection
        r_ssrf = await client.post("/api/v1/resolve", json={"url": "http://169.254.169.254/latest"})
        assert r_ssrf.status_code == 400
        assert r_ssrf.json()["error"]["code"] == "UNSUPPORTED"

        # 3. Resolve + Redis cache hit
        yt_url = "https://youtu.be/jNQXAC9IVRw?si=track123"
        r_res1 = await client.post("/api/v1/resolve", json={"url": yt_url})
        assert r_res1.status_code == 200
        body1 = r_res1.json()
        assert body1["platform"] == "youtube"
        assert body1["cached"] is False
        assert extractor.resolve_calls == 1

        r_res2 = await client.post("/api/v1/resolve", json={"url": yt_url})
        assert r_res2.status_code == 200
        assert r_res2.json()["cached"] is True
        assert extractor.resolve_calls == 1  # served from Redis cache

        # 4. Create job + idempotency
        r_job1 = await client.post("/api/v1/jobs", json={"url": yt_url, "preset": "best"})
        assert r_job1.status_code == 202
        job_id = r_job1.json()["job_id"]
        assert r_job1.json()["reused"] is False

        r_job2 = await client.post("/api/v1/jobs", json={"url": yt_url, "preset": "best"})
        assert r_job2.status_code == 202
        assert r_job2.json()["job_id"] == job_id
        assert r_job2.json()["reused"] is True

        # Wait for worker task to finish
        await asyncio.gather(*queued_tasks)

        # 5. Status snapshot + SSE
        r_snap = await client.get(f"/api/v1/jobs/{job_id}")
        assert r_snap.status_code == 200
        snap = r_snap.json()
        assert snap["status"] == "ready"
        assert snap["download_url"].startswith("/api/v1/files/")

        r_sse = await client.get(f"/api/v1/jobs/{job_id}/events")
        assert r_sse.status_code == 200
        assert "event: progress" in r_sse.text
        assert '"status":"ready"' in r_sse.text

        # 6. Full file download + Range (206) support + RFC 5987 Content-Disposition
        r_dl = await client.get(snap["download_url"])
        assert r_dl.status_code == 200
        assert len(r_dl.content) == 1024
        assert "filename*=UTF-8''" in r_dl.headers["content-disposition"]
        assert r_dl.headers["accept-ranges"] == "bytes"

        r_range = await client.get(snap["download_url"], headers={"Range": "bytes=0-15"})
        assert r_range.status_code == 206
        assert r_range.content == b"0123456789ABCDEF"
        assert r_range.headers["content-range"] == "bytes 0-15/1024"

        # 7. Cancel & cleanup deletes file on disk
        r_del = await client.delete(f"/api/v1/jobs/{job_id}")
        assert r_del.status_code == 200
        assert not (test_settings.storage_dir / job_id).exists()

        r_after_del = await client.get(snap["download_url"])
        assert r_after_del.status_code == 410

        # 8. Rate limit enforcement
        test_settings.rate_limit_resolve_per_minute = 2
        for _ in range(25):
            r_rl = await client.post("/api/v1/resolve", json={"url": yt_url})
            if r_rl.status_code == 429:
                assert r_rl.json()["error"]["code"] == "RATE_LIMITED"
                assert r_rl.json()["error"]["retryable"] is True
                break
        else:
            pytest.fail("Expected 429 rate limit response")
