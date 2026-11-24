"""SSRF protection: strict hostname allowlist, DNS IP validation, and safe redirect following."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from app.errors import AppError, ErrorCode

# Exact allowlisted hosts and allowlisted parent domains for the 4 supported platforms + shorteners
ALLOWED_DOMAINS: frozenset[str] = frozenset(
    {
        # YouTube
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
        # X / Twitter
        "x.com",
        "twitter.com",
        "t.co",
        "fxtwitter.com",
        "vxtwitter.com",
        # Instagram
        "instagram.com",
        "instagr.am",
        # Facebook
        "facebook.com",
        "fb.watch",
        "fb.com",
        "fb.gg",
    }
)

SHORTENER_DOMAINS: frozenset[str] = frozenset(
    {
        "youtu.be",
        "t.co",
        "instagr.am",
        "fb.watch",
        "fb.com",
        "fb.gg",
    }
)

# Cloud metadata / link-local / private / loopback / reserved ranges are all caught by Python ipaddress
_METADATA_IPS = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("169.254.170.2"),
        ipaddress.ip_address("100.100.100.200"),
        ipaddress.ip_address("fd00:ec2::254"),
    }
)

MAX_REDIRECT_HOPS = 5


def is_host_allowed(hostname: str) -> bool:
    """Check if hostname exactly matches or is a subdomain of an allowlisted platform domain."""
    host = hostname.strip().lower().rstrip(".")
    if not host:
        return False
    # Reject raw IP literals immediately
    try:
        ipaddress.ip_address(host.strip("[]"))
        return False
    except ValueError:
        pass

    return any(host == domain or host.endswith(f".{domain}") for domain in ALLOWED_DOMAINS)


def is_ip_public_and_safe(ip_str: str) -> bool:
    """Return True only if the resolved IP is a globally routable public IP."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    # Handle IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    if ip in _METADATA_IPS:
        return False
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    return ip.is_global


def validate_url_syntax(raw_url: str) -> str:
    """Validate URL syntax, scheme, credentials, port, and hostname allowlist."""
    url = raw_url.strip()
    if not url or len(url) > 2048:
        raise AppError(
            code=ErrorCode.INVALID_URL,
            message="Please enter a valid video URL.",
            hint="URLs must start with http:// or https:// and be under 2048 characters.",
            status_code=400,
        )

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise AppError(
            code=ErrorCode.INVALID_URL,
            message="Only http and https URLs are supported.",
            hint="Paste a direct public link starting with https://.",
            status_code=400,
        )

    if parsed.username or parsed.password:
        raise AppError(
            code=ErrorCode.SSRF_BLOCKED,
            message="URLs containing embedded credentials are not allowed.",
            hint="Remove username/password credentials from the URL.",
            status_code=400,
        )

    if parsed.port is not None and parsed.port not in {80, 443}:
        raise AppError(
            code=ErrorCode.SSRF_BLOCKED,
            message="Non-standard ports are not allowed.",
            hint="Use standard platform URLs without custom port numbers.",
            status_code=400,
        )

    hostname = parsed.hostname or ""
    if not is_host_allowed(hostname):
        raise AppError(
            code=ErrorCode.UNSUPPORTED,
            message="This website is not supported.",
            hint="Supported platforms: YouTube, X (Twitter), Instagram, and Facebook.",
            status_code=400,
        )

    return url


def _resolve_host_sync(hostname: str) -> list[str]:
    infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    ips: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            ips.append(str(sockaddr[0]))
    return list(dict.fromkeys(ips))


async def assert_dns_safe(hostname: str) -> list[str]:
    """Resolve DNS and reject any private/loopback/link-local/metadata IP."""
    try:
        ips = await asyncio.to_thread(_resolve_host_sync, hostname)
    except socket.gaierror as exc:
        raise AppError(
            code=ErrorCode.NETWORK,
            message=f"Could not resolve hostname '{hostname}'.",
            hint="Check the link or try again in a moment.",
            retryable=True,
            status_code=502,
        ) from exc

    if not ips:
        raise AppError(
            code=ErrorCode.SSRF_BLOCKED,
            message="Hostname did not resolve to any valid address.",
            hint="Verify the URL is valid.",
            status_code=400,
        )

    for ip_str in ips:
        if not is_ip_public_and_safe(ip_str):
            raise AppError(
                code=ErrorCode.SSRF_BLOCKED,
                message="Target address is blocked by security policy.",
                hint="Only public platform URLs are allowed.",
                status_code=403,
            )

    return ips


def _is_redirect_or_share_url(hostname: str, path: str) -> bool:
    """Return True if the URL is a known shortener or platform /share/ redirect link."""
    if any(hostname == dom or hostname.endswith(f".{dom}") for dom in SHORTENER_DOMAINS):
        return True
    if (hostname == "facebook.com" or hostname.endswith(".facebook.com")) and (
        path.startswith("/share/") or path.rstrip("/") in {"/login", "/login.php", "/flx/warn"}
    ):
        return True
    return (hostname == "instagram.com" or hostname.endswith(".instagram.com")) and path.startswith("/share/")


def _unwrap_login_redirect(url: str) -> str | None:
    """If Facebook redirects a public share/video link to /login/?next=..., extract the inner target URL."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if not (host == "facebook.com" or host.endswith(".facebook.com")):
        return None
    path = parsed.path.rstrip("/")
    q = parse_qs(parsed.query, keep_blank_values=False)
    if path in {"/login", "/login.php"} and q.get("next"):
        candidate = q["next"][0].strip()
        if candidate.startswith(("http://", "https://")):
            return candidate
    if path == "/flx/warn" and q.get("u"):
        candidate = q["u"][0].strip()
        if candidate.startswith(("http://", "https://")):
            return candidate
    return None


async def validate_and_resolve_url(
    raw_url: str,
    *,
    follow_short_links: bool = True,
    proxy: str | None = None,
    timeout_seconds: float = 8.0,
) -> str:
    """
    Validate URL against allowlist and DNS rules.
    If the URL is a known short link (t.co, fb.watch, instagr.am, youtu.be) or platform
    share link (facebook.com/share/..., instagram.com/share/...), follow redirects manually
    hop-by-hop, re-validating hostname allowlist and DNS IPs on every hop.
    """
    current_url = validate_url_syntax(raw_url)
    unwrapped = _unwrap_login_redirect(current_url)
    if unwrapped:
        current_url = validate_url_syntax(unwrapped)

    parsed = urlparse(current_url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    path = parsed.path or "/"
    await assert_dns_safe(hostname)

    if not follow_short_links or not _is_redirect_or_share_url(hostname, path):
        return current_url

    # youtu.be doesn't need an HTTP round-trip; yt-dlp and our normalizer handle it natively
    if hostname == "youtu.be" or hostname.endswith(".youtu.be"):
        return current_url

    is_fb = hostname in {"fb.watch", "fb.com", "fb.gg"} or hostname == "facebook.com" or hostname.endswith(".facebook.com")
    user_agent = (
        "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
        if is_fb
        else (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
    )

    client_kwargs: dict[str, object] = {
        "follow_redirects": False,
        "timeout": timeout_seconds,
        "headers": {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
        for _ in range(MAX_REDIRECT_HOPS):
            try:
                if is_fb:
                    resp = await client.get(current_url)
                else:
                    resp = await client.head(current_url)
                    if resp.status_code in {405, 403, 400}:
                        resp = await client.get(current_url)
            except httpx.HTTPError:
                # Fall back to the already-validated URL if shortener blocks HEAD/GET
                return current_url

            if resp.status_code not in {301, 302, 303, 307, 308}:
                return current_url

            location = resp.headers.get("location")
            if not location:
                return current_url

            next_url = urljoin(current_url, location)
            unwrapped_next = _unwrap_login_redirect(next_url)
            if unwrapped_next:
                next_url = unwrapped_next

            current_url = validate_url_syntax(next_url)
            next_parsed = urlparse(current_url)
            next_host = (next_parsed.hostname or "").lower().rstrip(".")
            next_path = next_parsed.path or "/"
            await assert_dns_safe(next_host)

            if not _is_redirect_or_share_url(next_host, next_path):
                return current_url

    return current_url
