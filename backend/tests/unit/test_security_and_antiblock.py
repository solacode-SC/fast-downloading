"""Unit tests for filename sanitization, RFC 5987 headers, HMAC tokens, ProxyPool, and CircuitBreaker."""

from __future__ import annotations

import pytest
from app.errors import AppError, ErrorCode
from app.schemas import Platform
from app.security.sanitize import build_content_disposition, sanitize_filename
from app.security.tokens import create_download_token, verify_download_token
from app.services.circuit_breaker import CircuitBreaker
from app.services.proxies import ProxyPool, mask_proxy_label


def test_sanitize_filename_and_header() -> None:
    assert sanitize_filename("../../etc/passwd", "mp4") == "etc passwd.mp4"
    assert sanitize_filename("CON", "mp4") == "_CON.mp4"
    assert sanitize_filename("Hello\x00World: Test?*", "mkv") == "HelloWorld Test.mkv"
    assert sanitize_filename("فيديو عربي رائع 🎬", "mp4").endswith(".mp4")
    assert len(sanitize_filename("a" * 300, "mp4")) <= 125

    cd = build_content_disposition("Café فيديو.mp4")
    assert "attachment;" in cd
    assert 'filename="' in cd
    assert "filename*=UTF-8''" in cd


def test_hmac_tokens() -> None:
    secret = "super-secret-signing-key-32-bytes"
    tok = create_download_token(job_id="job123", kind="media", secret=secret, ttl_seconds=60, now=1000)
    payload = verify_download_token(tok, secret=secret, now=1030)
    assert payload["j"] == "job123"
    assert payload["k"] == "media"

    # Expired token
    with pytest.raises(AppError) as exp_err:
        verify_download_token(tok, secret=secret, now=1061)
    assert exp_err.value.code == ErrorCode.FILE_EXPIRED

    # Tampered token
    tampered = tok[:-2] + ("AA" if not tok.endswith("AA") else "BB")
    with pytest.raises(AppError) as bad_err:
        verify_download_token(tampered, secret=secret, now=1030)
    assert bad_err.value.code == ErrorCode.INVALID_TOKEN


def test_proxy_pool_ejection_and_readmission() -> None:
    assert mask_proxy_label("http://user:supersecret@proxy1.example.com:8080") == "http://proxy1.example.com:8080"

    pool = ProxyPool(
        platform_proxies={
            Platform.YOUTUBE: [
                "http://u:p@p1.example.com:8080",
                "http://u:p@p2.example.com:8080",
            ],
            Platform.X: [],
            Platform.INSTAGRAM: [],
            Platform.FACEBOOK: [],
        },
        strategy="round_robin",
        max_failures=2,
        cooldown_seconds=60,
    )
    assert pool.healthy_count(Platform.YOUTUBE, now=1000) == 2

    # Eject p1 after 2 failures
    pool.record_failure(Platform.YOUTUBE, "http://u:p@p1.example.com:8080", now=1000)
    pool.record_failure(Platform.YOUTUBE, "http://u:p@p1.example.com:8080", now=1001)
    assert pool.healthy_count(Platform.YOUTUBE, now=1005) == 1

    chosen = pool.select(Platform.YOUTUBE, now=1005)
    assert chosen is not None
    assert chosen.label == "http://p2.example.com:8080"

    # Re-admitted after cooldown expires (1001 + 60 = 1061)
    assert pool.healthy_count(Platform.YOUTUBE, now=1062) == 2


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_recovers(fake_redis) -> None:  # type: ignore[no-untyped-def]
    cb = CircuitBreaker(fake_redis, threshold=2, cooldown_seconds=30)
    await cb.assert_closed(Platform.INSTAGRAM, "direct")

    tripped1 = await cb.record_failure(Platform.INSTAGRAM, "direct")
    assert tripped1 is False
    tripped2 = await cb.record_failure(Platform.INSTAGRAM, "direct")
    assert tripped2 is True

    with pytest.raises(AppError) as err:
        await cb.assert_closed(Platform.INSTAGRAM, "direct")
    assert err.value.code == ErrorCode.CIRCUIT_OPEN
    assert "try again in" in err.value.hint.lower()

    await cb.record_success(Platform.INSTAGRAM, "direct")
    await cb.assert_closed(Platform.INSTAGRAM, "direct")
