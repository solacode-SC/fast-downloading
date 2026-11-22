"""Unit tests for format parsing, preset building, and yt-dlp format selection."""

from __future__ import annotations

from app.schemas import Platform, Preset
from app.services.formats import build_presets, build_ytdlp_format_options, parse_formats


def test_parse_formats_and_presets() -> None:
    sample_info = {
        "duration": 120,
        "formats": [
            {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none"},
            {
                "format_id": "313",
                "ext": "webm",
                "width": 3840,
                "height": 2160,
                "fps": 60,
                "vcodec": "vp09.02.51",
                "acodec": "none",
                "dynamic_range": "HDR10",
                "tbr": 18000,
                "filesize": 250_000_000,
            },
            {
                "format_id": "137",
                "ext": "mp4",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "vcodec": "avc1.640028",
                "acodec": "none",
                "tbr": 4200,
                "filesize": 60_000_000,
            },
            {
                "format_id": "140",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "abr": 128,
                "filesize": 2_000_000,
            },
        ],
    }

    fmts = parse_formats(sample_info)
    assert len(fmts) == 3  # storyboard skipped
    assert fmts[0].format_id == "313"
    assert fmts[0].is_hdr is True
    assert fmts[0].vcodec == "vp9"
    assert fmts[1].format_id == "137"
    assert fmts[1].vcodec == "avc1"
    assert fmts[2].is_audio_only is True
    assert fmts[2].acodec == "aac"

    presets = build_presets(fmts)
    preset_map = {p.id: p for p in presets}
    assert preset_map[Preset.BEST].estimated_height == 2160
    assert preset_map[Preset.COMPATIBLE].estimated_height == 1080
    assert preset_map[Preset.COMPATIBLE].estimated_ext == "mp4"
    assert Preset.AUDIO_M4A in preset_map
    assert Preset.AUDIO_MP3_320 in preset_map


def test_build_ytdlp_format_options() -> None:
    best_yt = build_ytdlp_format_options(platform=Platform.YOUTUBE, preset=Preset.BEST, format_id=None)
    assert "bestvideo" in best_yt["format"]
    assert best_yt["merge_output_format"] == "mkv/mp4"

    compat = build_ytdlp_format_options(platform=Platform.YOUTUBE, preset=Preset.COMPATIBLE, format_id=None)
    assert "avc1" in compat["format"]
    assert compat["merge_output_format"] == "mp4"

    audio_mp3 = build_ytdlp_format_options(platform=Platform.YOUTUBE, preset=Preset.AUDIO_MP3_320, format_id=None)
    assert audio_mp3["postprocessors"][0]["preferredcodec"] == "mp3"
    assert audio_mp3["postprocessors"][0]["preferredquality"] == "320"

    custom = build_ytdlp_format_options(platform=Platform.YOUTUBE, preset=None, format_id="137;rm -rf /")
    # Shell metacharacters stripped
    assert ";" not in custom["format"]
    assert " " not in custom["format"]
