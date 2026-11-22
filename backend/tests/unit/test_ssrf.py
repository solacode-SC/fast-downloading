"""Unit tests for SSRF protection and URL allowlist."""

from __future__ import annotations

import pytest
from app.errors import AppError, ErrorCode
from app.security.ssrf import (
    assert_dns_safe,
    is_host_allowed,
    is_ip_public_and_safe,
    validate_url_syntax,
)


@pytest.mark.parametrize(
    "host",
    [
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "x.com",
        "twitter.com",
        "mobile.twitter.com",
        "t.co",
        "instagram.com",
        "www.instagram.com",
        "instagr.am",
        "facebook.com",
        "m.facebook.com",
        "fb.watch",
    ],
)
def test_allowed_hosts(host: str) -> None:
    assert is_host_allowed(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "127.0.0.1",
        "169.254.169.254",
        "evil-youtube.com",
        "youtube.com.evil.org",
        "internal.local",
        "example.com",
        "[::1]",
        "",
    ],
)
def test_disallowed_hosts(host: str) -> None:
    assert is_host_allowed(host) is False


@pytest.mark.parametrize(
    ("ip", "expected"),
    [
        ("8.8.8.8", True),
        ("142.250.190.46", True),
        ("2606:4700:4700::1111", True),
        ("127.0.0.1", False),
        ("10.0.0.1", False),
        ("172.16.0.5", False),
        ("192.168.1.10", False),
        ("169.254.169.254", False),
        ("0.0.0.0", False),
        ("::1", False),
        ("fe80::1", False),
        ("fc00::1", False),
        ("::ffff:127.0.0.1", False),
        ("::ffff:169.254.169.254", False),
    ],
)
def test_ip_safety(ip: str, expected: bool) -> None:
    assert is_ip_public_and_safe(ip) is expected


def test_validate_url_rejects_bad_scheme_credentials_ports() -> None:
    with pytest.raises(AppError) as exc1:
        validate_url_syntax("file:///etc/passwd")
    assert exc1.value.code == ErrorCode.INVALID_URL

    with pytest.raises(AppError) as exc2:
        validate_url_syntax("https://user:pass@youtube.com/watch?v=dQw4w9WgXcQ")
    assert exc2.value.code == ErrorCode.SSRF_BLOCKED

    with pytest.raises(AppError) as exc3:
        validate_url_syntax("https://youtube.com:8443/watch?v=dQw4w9WgXcQ")
    assert exc3.value.code == ErrorCode.SSRF_BLOCKED

    with pytest.raises(AppError) as exc4:
        validate_url_syntax("https://169.254.169.254/latest/meta-data/")
    assert exc4.value.code == ErrorCode.UNSUPPORTED


@pytest.mark.asyncio
async def test_assert_dns_safe_blocks_private_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.security.ssrf._resolve_host_sync", lambda _h: ["127.0.0.1"])
    with pytest.raises(AppError) as exc:
        await assert_dns_safe("youtube.com")
    assert exc.value.code == ErrorCode.SSRF_BLOCKED


@pytest.mark.asyncio
async def test_assert_dns_safe_allows_public_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.security.ssrf._resolve_host_sync", lambda _h: ["142.250.190.46"])
    ips = await assert_dns_safe("youtube.com")
    assert ips == ["142.250.190.46"]
