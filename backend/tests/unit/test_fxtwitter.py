"""Unit tests for X (Twitter) fxtwitter fast-path helper."""

from __future__ import annotations

from app.schemas import Preset
from app.services.fxtwitter import (
    _parse_video_formats,
    _select_x_variant,
    extract_tweet_id,
    is_safe_twimg_url,
)


def test_extract_tweet_id() -> None:
    assert extract_tweet_id("https://x.com/ilanzraee/status/2123872904035365018") == "2123872904035365018"
    assert extract_tweet_id("https://twitter.com/i/statuses/719944021058060289") == "719944021058060289"
    assert extract_tweet_id("https://x.com/home") is None


def test_is_safe_twimg_url() -> None:
    assert is_safe_twimg_url("https://video.twimg.com/amplify_video/123/vid/avc1/720x1280/a.mp4") is True
    assert is_safe_twimg_url("https://pbs.twimg.com/media/abc.jpg") is True
    assert is_safe_twimg_url("http://video.twimg.com/insecure.mp4") is False
    assert is_safe_twimg_url("https://evil-twimg.com/a.mp4") is False
    assert is_safe_twimg_url("https://169.254.169.254/a.mp4") is False


def test_parse_and_select_x_variants() -> None:
    video_payload = {
        "width": 720,
        "height": 1280,
        "formats": [
            {
                "url": "https://video.twimg.com/amplify_video/1/pl/main.m3u8",
                "container": "m3u8",
            },
            {
                "url": "https://video.twimg.com/amplify_video/1/vid/avc1/480x852/med.mp4",
                "bitrate": 950000,
                "container": "mp4",
            },
            {
                "url": "https://video.twimg.com/amplify_video/1/vid/avc1/720x1280/hd.mp4",
                "bitrate": 2176000,
                "container": "mp4",
            },
        ],
    }
    fmts = _parse_video_formats(video_payload, 30.0)
    assert len(fmts) == 2
    assert fmts[0]["format_id"] == "http-2176"
    assert fmts[0]["height"] == 1280
    assert fmts[1]["format_id"] == "http-950"

    best = _select_x_variant(fmts, Preset.BEST, None)
    assert best["format_id"] == "http-2176"

    p480 = _select_x_variant(fmts, Preset.P480, None)
    assert p480["format_id"] == "http-950"

    explicit = _select_x_variant(fmts, None, "http-950")
    assert explicit["format_id"] == "http-950"
