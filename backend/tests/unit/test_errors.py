"""Unit tests for yt-dlp error classification (L7)."""

from __future__ import annotations

import pytest
from app.errors import ErrorCode, classify_ytdlp_error


@pytest.mark.parametrize(
    ("raw_msg", "expected_code", "expected_retryable"),
    [
        ("Sign in to confirm you're not a bot. This helps protect our community.", ErrorCode.BOT_CHECK, True),
        (
            "Sign in to confirm your age. This video may be inappropriate for some users.",
            ErrorCode.AGE_RESTRICTED,
            False,
        ),
        ("This video is private.", ErrorCode.PRIVATE, False),
        ("Instagram sent an empty media response. Login required.", ErrorCode.LOGIN_REQUIRED, True),
        ("The uploader has not made this video available in your country.", ErrorCode.GEO_BLOCKED, True),
        ("Video unavailable. This video has been removed by the uploader.", ErrorCode.REMOVED, False),
        ("HTTP Error 429: Too Many Requests", ErrorCode.RATE_LIMITED, True),
        ("This live event will begin in 30 minutes.", ErrorCode.LIVE_STREAM, False),
        ("This video is DRM protected (Widevine).", ErrorCode.DRM_PROTECTED, False),
        ("Unsupported URL: https://example.com/foo", ErrorCode.UNSUPPORTED, False),
        ("Unable to download webpage: timed out", ErrorCode.NETWORK, True),
    ],
)
def test_error_classification(raw_msg: str, expected_code: ErrorCode, expected_retryable: bool) -> None:
    err = classify_ytdlp_error(RuntimeError(raw_msg))
    assert err.code == expected_code
    assert err.retryable is expected_retryable
    assert err.message
    assert err.hint
