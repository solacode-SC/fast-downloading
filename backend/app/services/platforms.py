"""Platform detection, URL normalization, and yt-dlp extractor allowlists."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.errors import AppError, ErrorCode
from app.schemas import Platform

_PLATFORM_HOSTS: dict[Platform, tuple[str, ...]] = {
    Platform.YOUTUBE: ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    Platform.X: ("x.com", "twitter.com", "t.co", "fxtwitter.com", "vxtwitter.com"),
    Platform.INSTAGRAM: ("instagram.com", "instagr.am"),
    Platform.FACEBOOK: ("facebook.com", "fb.watch", "fb.com", "fb.gg"),
}

# Restrict yt-dlp to only the extractors needed for the 4 supported platforms (defense in depth)
ALLOWED_YTDLP_EXTRACTORS: dict[Platform, list[str]] = {
    Platform.YOUTUBE: [
        "youtube",
        "youtube:tab",
        "youtube:playlist",
        "youtube:shorts",
        "youtube:clip",
        "youtube:consent",
        "YoutubeYtBe",
        "YoutubeLivestreamEmbed",
        "generic",
    ],
    Platform.X: [
        "twitter",
        "twitter:card",
        "twitter:amplify",
        "twitter:broadcast",
        "twitter:spaces",
        "twitter:shortener",
        "generic",
    ],
    Platform.INSTAGRAM: [
        "instagram",
        "Instagram",
        "instagram:story",
        "instagram:reel",
        "InstagramIOS",
        "generic",
    ],
    Platform.FACEBOOK: [
        "facebook",
        "facebook:reel",
        "facebook:ads",
        "FacebookPluginsVideo",
        "FacebookRedirectURL",
        "generic",
    ],
}

_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "si",
        "igsh",
        "igshid",
        "fbclid",
        "mibextid",
        "s",
        "t",
        "ref",
        "ref_src",
        "ref_url",
        "feature",
        "pp",
    }
)

_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def detect_platform(url: str) -> Platform:
    """Detect which supported platform a validated URL belongs to."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    for platform, domains in _PLATFORM_HOSTS.items():
        for domain in domains:
            if host == domain or host.endswith(f".{domain}"):
                return platform

    raise AppError(
        code=ErrorCode.UNSUPPORTED,
        message="Unsupported platform URL.",
        hint="Supported platforms: YouTube, X (Twitter), Instagram, and Facebook.",
        status_code=400,
    )


def normalize_url(url: str, platform: Platform) -> str:
    """
    Canonicalize a URL for cache keys, idempotency, and cleaner extraction:
    - Strip tracking parameters (utm_*, si, igsh, fbclid, etc.)
    - Convert youtu.be/<id> -> https://www.youtube.com/watch?v=<id>
    - Convert fxtwitter.com/vxtwitter.com/twitter.com -> https://x.com/...
    - Normalize scheme to https
    """
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    path = parsed.path or "/"
    query_dict = parse_qs(parsed.query, keep_blank_values=False)

    # Strip tracking params (keep YouTube 't' only if not stripping? No, cache shouldn't fragment on timestamps)
    cleaned_query: dict[str, list[str]] = {k: v for k, v in query_dict.items() if k.lower() not in _TRACKING_PARAMS}

    if platform == Platform.YOUTUBE:
        if host == "youtu.be" or host.endswith(".youtu.be"):
            vid = path.strip("/").split("/")[0]
            if _YT_ID_RE.match(vid):
                new_q = {"v": [vid]}
                if "list" in cleaned_query:
                    new_q["list"] = cleaned_query["list"]
                return urlunparse(("https", "www.youtube.com", "/watch", "", urlencode(new_q, doseq=True), ""))
        if host in {"m.youtube.com", "youtube.com", "music.youtube.com"}:
            host = "www.youtube.com"
        return urlunparse(("https", host, path.rstrip("/") or "/", "", urlencode(cleaned_query, doseq=True), ""))

    if platform == Platform.X:
        if host in {
            "twitter.com",
            "www.twitter.com",
            "mobile.twitter.com",
            "fxtwitter.com",
            "vxtwitter.com",
            "www.x.com",
            "mobile.x.com",
        }:
            host = "x.com"
        return urlunparse(("https", host, path.rstrip("/") or "/", "", "", ""))

    if platform == Platform.INSTAGRAM:
        if host in {"instagram.com", "m.instagram.com"}:
            host = "www.instagram.com"
        clean_path = path if path.endswith("/") else f"{path}/"
        return urlunparse(("https", host, clean_path, "", "", ""))

    if platform == Platform.FACEBOOK:
        # Unwrap Facebook login or external link wrapper query params (?next=... or ?u=...)
        if path.rstrip("/") in {"/login", "/login.php"} and "next" in query_dict and query_dict["next"]:
            inner = query_dict["next"][0]
            if inner.startswith(("http://", "https://")) and detect_platform(inner) == Platform.FACEBOOK:
                return normalize_url(inner, Platform.FACEBOOK)
        if path.rstrip("/") == "/flx/warn" and "u" in query_dict and query_dict["u"]:
            inner = query_dict["u"][0]
            if inner.startswith(("http://", "https://")) and detect_platform(inner) == Platform.FACEBOOK:
                return normalize_url(inner, Platform.FACEBOOK)

        if host in {"m.facebook.com", "facebook.com", "web.facebook.com"}:
            host = "www.facebook.com"
        if path.startswith("/reels/"):
            path = "/reel/" + path[len("/reels/") :]
        watch_id_match = re.match(r"^/watch/(\d+)/?$", path)
        if watch_id_match:
            path = "/watch/"
            cleaned_query["v"] = [watch_id_match.group(1)]
        return urlunparse(("https", host, path, "", urlencode(cleaned_query, doseq=True), ""))

    return urlunparse(("https", host, path, "", urlencode(cleaned_query, doseq=True), ""))
