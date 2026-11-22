"""Unit tests for platform detection and URL normalization."""

from __future__ import annotations

import pytest
from app.schemas import Platform
from app.services.platforms import detect_platform, normalize_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=jNQXAC9IVRw", Platform.YOUTUBE),
        ("https://youtu.be/jNQXAC9IVRw?si=abc123", Platform.YOUTUBE),
        ("https://x.com/NASA/status/1234567890", Platform.X),
        ("https://twitter.com/NASA/status/1234567890", Platform.X),
        ("https://www.instagram.com/reel/C-x8zY_y2kM/", Platform.INSTAGRAM),
        ("https://www.facebook.com/watch/?v=10153231379946729", Platform.FACEBOOK),
        ("https://fb.watch/abcdef/", Platform.FACEBOOK),
    ],
)
def test_detect_platform(url: str, expected: Platform) -> None:
    assert detect_platform(url) == expected


def test_normalize_urls_strip_tracking_and_canonicalize() -> None:
    assert (
        normalize_url("https://youtu.be/jNQXAC9IVRw?si=xyz", Platform.YOUTUBE)
        == "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    )
    assert (
        normalize_url("https://twitter.com/NASA/status/12345?s=20&t=abc", Platform.X)
        == "https://x.com/NASA/status/12345"
    )
    assert (
        normalize_url("https://instagram.com/reel/ABC123?igsh=foo", Platform.INSTAGRAM)
        == "https://www.instagram.com/reel/ABC123/"
    )
    assert (
        normalize_url("https://m.facebook.com/watch/?v=999&fbclid=xyz", Platform.FACEBOOK)
        == "https://www.facebook.com/watch/?v=999"
    )
