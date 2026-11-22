"""Typed application errors and yt-dlp error classifier (Anti-Block L7)."""

from __future__ import annotations

import re
from enum import StrEnum

from app.schemas import ErrorDetail, ErrorResponse


class ErrorCode(StrEnum):
    INVALID_URL = "INVALID_URL"
    UNSUPPORTED = "UNSUPPORTED"
    SSRF_BLOCKED = "SSRF_BLOCKED"
    BOT_CHECK = "BOT_CHECK"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    AGE_RESTRICTED = "AGE_RESTRICTED"
    GEO_BLOCKED = "GEO_BLOCKED"
    PRIVATE = "PRIVATE"
    REMOVED = "REMOVED"
    LIVE_STREAM = "LIVE_STREAM"
    DRM_PROTECTED = "DRM_PROTECTED"
    RATE_LIMITED = "RATE_LIMITED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    TOO_LONG = "TOO_LONG"
    TOO_LARGE = "TOO_LARGE"
    DISK_FULL = "DISK_FULL"
    NETWORK = "NETWORK"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    FILE_EXPIRED = "FILE_EXPIRED"
    INVALID_TOKEN = "INVALID_TOKEN"  # noqa: S105
    TURNSTILE_FAILED = "TURNSTILE_FAILED"
    CANCELLED = "CANCELLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        hint: str = "",
        retryable: bool = False,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.retryable = retryable
        self.status_code = status_code

    def to_detail(self) -> ErrorDetail:
        return ErrorDetail(
            code=self.code.value,
            message=self.message,
            hint=self.hint,
            retryable=self.retryable,
        )

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(error=self.to_detail())


# Ordered pattern rules for classifying yt-dlp exceptions accurately
_CLASSIFICATION_RULES: list[tuple[re.Pattern[str], ErrorCode, str, str, bool, int]] = [
    (
        re.compile(r"drm|widevine|fairplay|playready|encrypted\s+stream", re.IGNORECASE),
        ErrorCode.DRM_PROTECTED,
        "This media is DRM-protected and cannot be downloaded.",
        "Only public, non-DRM content is supported.",
        False,
        422,
    ),
    (
        re.compile(
            r"sign in to confirm you['’]?re not a bot|confirm you are not a bot|bot\s+check|captcha|challenge|automated\s+queries|po\s*token|page needs to be reloaded",
            re.IGNORECASE,
        ),
        ErrorCode.BOT_CHECK,
        "The platform triggered an anti-bot verification check.",
        "Please retry in a moment. If running on a VPS, enable PO tokens, WARP, or a residential proxy.",
        True,
        503,
    ),
    (
        re.compile(
            r"sign in to confirm your age|age[- ]restricted|confirm your age|inappropriate for some users|nsfw|sensitive content",
            re.IGNORECASE,
        ),
        ErrorCode.AGE_RESTRICTED,
        "This video is age-restricted on the source platform.",
        "Age-restricted videos require platform authentication and cannot be downloaded anonymously.",
        False,
        403,
    ),
    (
        re.compile(
            r"private video|this video is private|account is private|protected tweets|only visible to followers|must be logged in to view this private",
            re.IGNORECASE,
        ),
        ErrorCode.PRIVATE,
        "This content is private and cannot be accessed.",
        "Only public videos are supported.",
        False,
        403,
    ),
    (
        re.compile(
            r"login required|log in to continue|cookies.*required|requested content is not available.*login|there is no video in this tweet.*login|empty media response|instagram sent an empty media response",
            re.IGNORECASE,
        ),
        ErrorCode.LOGIN_REQUIRED,
        "The platform requires sign-in to access this post from this server IP.",
        "Retry shortly or configure optional platform cookies / residential egress proxy.",
        True,
        403,
    ),
    (
        re.compile(
            r"not available in your country|geo[- ]?restricted|blocked it in your country|uploader has not made this video available in your country",
            re.IGNORECASE,
        ),
        ErrorCode.GEO_BLOCKED,
        "This video is geo-blocked in the server's region.",
        "Use a proxy in an allowed region if you have permission to access this content.",
        True,
        451,
    ),
    (
        re.compile(
            r"video unavailable|has been removed|deleted|does not exist|no longer available|404|status.*not found|content isn't available|copyright claim|account.*terminated",
            re.IGNORECASE,
        ),
        ErrorCode.REMOVED,
        "This video was removed or is no longer available.",
        "Double-check the URL in your browser to confirm it is still public.",
        False,
        404,
    ),
    (
        re.compile(
            r"http error 429|too many requests|rate[- ]?limit|temporarily blocked|slow down",
            re.IGNORECASE,
        ),
        ErrorCode.RATE_LIMITED,
        "The source platform is rate-limiting requests right now.",
        "Wait a few seconds and try again.",
        True,
        429,
    ),
    (
        re.compile(
            r"this live event will begin|is live|live stream|premieres in",
            re.IGNORECASE,
        ),
        ErrorCode.LIVE_STREAM,
        "Active live streams and upcoming premieres are not supported.",
        "Wait until the live stream ends and try downloading the replay.",
        False,
        422,
    ),
    (
        re.compile(
            r"unsupported url|no video could be found|no video formats found|there is no video|unable to recognize",
            re.IGNORECASE,
        ),
        ErrorCode.UNSUPPORTED,
        "No downloadable public video was found at this URL.",
        "Make sure the link points directly to a public video post, reel, tweet, or YouTube video.",
        False,
        422,
    ),
    (
        re.compile(
            r"timed out|timeout|connection reset|connection refused|failed to connect|no route to host|network is unreachable|temporary failure in name resolution|ssl|eof occurred|http error 5\d\d|http error 403|forbidden|unable to download webpage|transporterror",
            re.IGNORECASE,
        ),
        ErrorCode.NETWORK,
        "A network error occurred while communicating with the platform.",
        "This is usually temporary. Please try again.",
        True,
        503,
    ),
]


def classify_ytdlp_error(exc: Exception | str) -> AppError:
    """Map raw yt-dlp error messages into structured, retry-aware AppError instances."""
    if isinstance(exc, AppError):
        return exc

    raw = str(exc).strip()
    for pattern, code, message, hint, retryable, status_code in _CLASSIFICATION_RULES:
        if pattern.search(raw):
            return AppError(
                code=code,
                message=message,
                hint=hint,
                retryable=retryable,
                status_code=status_code,
            )

    return AppError(
        code=ErrorCode.EXTRACTION_FAILED,
        message="Unable to extract media from this URL.",
        hint="Verify the URL is a public video from YouTube, X, Instagram, or Facebook and try again.",
        retryable=True,
        status_code=503,
    )


def is_auth_failure(error: AppError) -> bool:
    return error.code in {ErrorCode.LOGIN_REQUIRED, ErrorCode.BOT_CHECK}


def is_proxy_failure(error: AppError) -> bool:
    return error.code in {
        ErrorCode.BOT_CHECK,
        ErrorCode.RATE_LIMITED,
        ErrorCode.GEO_BLOCKED,
        ErrorCode.NETWORK,
        ErrorCode.LOGIN_REQUIRED,
    }
