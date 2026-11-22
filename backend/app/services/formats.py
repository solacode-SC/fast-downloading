"""Format parsing, quality preset construction, and yt-dlp format selector generation."""

from __future__ import annotations

from typing import Any

from app.schemas import FormatItem, MediaEntrySummary, Platform, Preset, PresetOption, SubtitleTrack


def _is_hdr(fmt: dict[str, Any]) -> bool:
    dr = str(fmt.get("dynamic_range") or "").upper()
    if dr and dr not in {"SDR", "NONE"}:
        return True
    vcodec = str(fmt.get("vcodec") or "").lower()
    note = str(fmt.get("format_note") or "").lower()
    return "hdr" in note or "vp9.2" in vcodec or "av01.0.09" in vcodec or "av01.0.12" in vcodec


def _short_codec(codec: str | None) -> str | None:
    if not codec or codec == "none":
        return None
    low = codec.lower()
    if low.startswith("avc1") or low.startswith("h264"):
        return "avc1"
    if low.startswith("vp09") or low.startswith("vp9"):
        return "vp9"
    if low.startswith("av01"):
        return "av01"
    if low.startswith("hev1") or low.startswith("hvc1") or low.startswith("hevc"):
        return "hevc"
    if low.startswith("mp4a"):
        return "aac"
    if low.startswith("opus"):
        return "opus"
    return low.split(".")[0]


def _estimate_size(fmt: dict[str, Any], duration: float | None) -> int | None:
    size = fmt.get("filesize")
    if isinstance(size, (int, float)) and size > 0:
        return int(size)
    approx = fmt.get("filesize_approx")
    if isinstance(approx, (int, float)) and approx > 0:
        return int(approx)
    tbr = fmt.get("tbr") or fmt.get("abr") or fmt.get("vbr")
    if isinstance(tbr, (int, float)) and tbr > 0 and duration and duration > 0:
        return int((float(tbr) * 1000.0 / 8.0) * float(duration))
    return None


def parse_formats(info: dict[str, Any]) -> list[FormatItem]:
    """Parse yt-dlp raw formats into clean, deduplicated, sorted FormatItem entries."""
    raw_formats = info.get("formats") or []
    duration = info.get("duration")
    items: list[FormatItem] = []

    for f in raw_formats:
        if not isinstance(f, dict):
            continue
        fmt_id = str(f.get("format_id") or "").strip()
        if not fmt_id:
            continue
        ext = str(f.get("ext") or "").lower()
        # Skip storyboards / mhtml / non-media metadata formats
        if ext in {"mhtml", "vtt", "srt", "jpg", "jpeg", "png", "webp"}:
            continue

        vcodec_raw = f.get("vcodec")
        acodec_raw = f.get("acodec")
        has_video = bool(vcodec_raw and str(vcodec_raw) != "none")
        has_audio = bool(acodec_raw and str(acodec_raw) != "none")

        # Some extractors (X/IG/FB) omit vcodec/acodec on progressive mp4 formats
        if not has_video and not has_audio:
            if ext in {"mp4", "webm", "mov", "mkv", "flv", "ts"} and (
                f.get("height") or f.get("width") or f.get("tbr") or f.get("url")
            ):
                has_video = True
                has_audio = True
            elif ext in {"m4a", "mp3", "opus", "ogg", "wav", "aac"}:
                has_audio = True
            else:
                continue

        width = int(f["width"]) if isinstance(f.get("width"), (int, float)) else None
        height = int(f["height"]) if isinstance(f.get("height"), (int, float)) else None
        fps = round(float(f["fps"]), 2) if isinstance(f.get("fps"), (int, float)) else None
        tbr = round(float(f["tbr"]), 1) if isinstance(f.get("tbr"), (int, float)) else None
        abr = round(float(f["abr"]), 1) if isinstance(f.get("abr"), (int, float)) else None
        vcodec = _short_codec(str(vcodec_raw) if has_video else None)
        acodec = _short_codec(str(acodec_raw) if has_audio else None)

        resolution = f"{height}p" if height else (f"{width}w" if width else ("audio" if not has_video else None))
        is_compatible = (ext == "mp4") and (vcodec in {None, "avc1"}) and (acodec in {None, "aac"})

        items.append(
            FormatItem(
                format_id=fmt_id,
                ext=ext or "mp4",
                resolution=resolution,
                width=width,
                height=height,
                fps=fps,
                vcodec=vcodec,
                acodec=acodec,
                is_hdr=_is_hdr(f),
                is_audio_only=(has_audio and not has_video),
                is_video_only=(has_video and not has_audio),
                is_progressive=(has_video and has_audio),
                tbr_kbps=tbr,
                abr_kbps=abr,
                filesize_bytes=int(f["filesize"]) if isinstance(f.get("filesize"), (int, float)) else None,
                filesize_approx_bytes=_estimate_size(f, float(duration) if duration else None),
                note=str(f.get("format_note") or "") or None,
                compatible=is_compatible,
            )
        )

    # Sort: video formats by height desc, fps desc, tbr desc; audio formats after by abr/tbr desc
    items.sort(
        key=lambda x: (
            0 if not x.is_audio_only else 1,
            -(x.height or 0),
            -(x.fps or 0.0),
            -(x.tbr_kbps or x.abr_kbps or 0.0),
        )
    )
    return items


def build_presets(formats: list[FormatItem]) -> list[PresetOption]:
    """Build user-friendly quality presets with accurate estimated heights and file sizes."""
    video_formats = [f for f in formats if not f.is_audio_only]
    audio_formats = [f for f in formats if f.is_audio_only]
    best_audio = audio_formats[0] if audio_formats else None
    best_audio_size = (best_audio.filesize_bytes or best_audio.filesize_approx_bytes or 0) if best_audio else 0

    def _estimate_for_cap(max_h: int | None, compatible_only: bool = False) -> tuple[int | None, int | None, str]:
        candidates = video_formats
        if max_h is not None:
            capped = [f for f in candidates if (f.height or 0) <= max_h]
            candidates = capped if capped else candidates
        if compatible_only:
            comp = [f for f in candidates if f.compatible or (f.ext == "mp4" and f.vcodec == "avc1")]
            if comp:
                candidates = comp
        if not candidates:
            return None, None, "mp4"
        top = candidates[0]
        v_size = top.filesize_bytes or top.filesize_approx_bytes
        total = None
        if v_size:
            total = v_size + (best_audio_size if top.is_video_only else 0)
        ext = "mp4" if (compatible_only or top.ext == "mp4") else ("mkv" if top.vcodec in {"vp9", "av01"} else top.ext)
        return top.height, total, ext

    max_avail_height = max((f.height or 0 for f in video_formats), default=0)

    best_h, best_sz, best_ext = _estimate_for_cap(None, compatible_only=False)
    comp_h, comp_sz, _ = _estimate_for_cap(None, compatible_only=True)

    presets: list[PresetOption] = [
        PresetOption(
            id=Preset.BEST,
            label="Best Available",
            description="Highest resolution & audio (VP9/AV1/H.264, stream-copied)",
            estimated_ext=best_ext,
            estimated_height=best_h,
            estimated_size_bytes=best_sz,
            available=bool(video_formats),
        ),
        PresetOption(
            id=Preset.COMPATIBLE,
            label="Best Compatible (MP4)",
            description="H.264 + AAC in MP4 for universal playback (iOS, macOS, TVs)",
            estimated_ext="mp4",
            estimated_height=comp_h,
            estimated_size_bytes=comp_sz,
            available=bool(video_formats),
        ),
    ]

    for preset_id, cap, label in (
        (Preset.P2160, 2160, "4K (2160p)"),
        (Preset.P1440, 1440, "1440p QHD"),
        (Preset.P1080, 1080, "1080p Full HD"),
        (Preset.P720, 720, "720p HD"),
        (Preset.P480, 480, "480p SD"),
    ):
        if max_avail_height == 0 or max_avail_height >= cap or cap <= 720:
            est_h, est_sz, est_ext = _estimate_for_cap(cap)
            presets.append(
                PresetOption(
                    id=preset_id,
                    label=label,
                    description=f"Up to {cap}p (graceful fallback if lower)",
                    estimated_ext=est_ext,
                    estimated_height=est_h,
                    estimated_size_bytes=est_sz,
                    available=bool(video_formats),
                )
            )

    presets.extend(
        [
            PresetOption(
                id=Preset.AUDIO_M4A,
                label="Audio Only (M4A)",
                description="Original AAC/M4A audio stream, no re-encode when available",
                estimated_ext="m4a",
                estimated_height=None,
                estimated_size_bytes=best_audio_size or None,
                available=True,
            ),
            PresetOption(
                id=Preset.AUDIO_MP3_320,
                label="Audio Only (MP3 320 kbps)",
                description="High-bitrate MP3 extracted via ffmpeg",
                estimated_ext="mp3",
                estimated_height=None,
                estimated_size_bytes=None,
                available=True,
            ),
            PresetOption(
                id=Preset.AUDIO_MP3_192,
                label="Audio Only (MP3 192 kbps)",
                description="Standard MP3 extracted via ffmpeg",
                estimated_ext="mp3",
                estimated_height=None,
                estimated_size_bytes=None,
                available=True,
            ),
        ]
    )

    return presets


def parse_subtitles(info: dict[str, Any]) -> list[SubtitleTrack]:
    """Extract available manual and auto subtitles (top languages, deduplicated)."""
    tracks: list[SubtitleTrack] = []
    seen: set[tuple[str, bool]] = set()

    for key, is_auto in (("subtitles", False), ("automatic_captions", True)):
        raw = info.get(key)
        if not isinstance(raw, dict):
            continue
        for lang, variants in raw.items():
            if not isinstance(lang, str) or lang == "live_chat":
                continue
            if (lang, is_auto) in seen:
                continue
            seen.add((lang, is_auto))
            name = lang
            if isinstance(variants, list) and variants and isinstance(variants[0], dict):
                name = str(variants[0].get("name") or lang)
            tracks.append(SubtitleTrack(lang=lang, name=name, ext="srt", auto=is_auto))
            if len(tracks) >= 40:
                return tracks

    return tracks


def parse_entries(info: dict[str, Any], max_items: int = 15) -> tuple[bool, bool, list[MediaEntrySummary]]:
    """Detect playlists and multi-video carousels (e.g. Instagram) and return bounded entries."""
    raw_entries = info.get("entries")
    if not isinstance(raw_entries, list) or len(raw_entries) == 0:
        return False, False, []

    is_carousel = str(info.get("extractor_key") or "").lower().startswith("instagram")
    is_playlist = not is_carousel
    entries: list[MediaEntrySummary] = []

    for idx, entry in enumerate(raw_entries[:max_items], start=1):
        if not isinstance(entry, dict):
            continue
        e_url = str(entry.get("webpage_url") or entry.get("url") or "")
        if not e_url:
            continue
        entries.append(
            MediaEntrySummary(
                index=idx,
                id=str(entry.get("id") or idx),
                title=str(entry.get("title") or f"Item {idx}"),
                url=e_url,
                duration_seconds=int(entry["duration"]) if isinstance(entry.get("duration"), (int, float)) else None,
                thumbnail_url=str(entry.get("thumbnail")) if entry.get("thumbnail") else None,
            )
        )

    return is_playlist, is_carousel, entries


def build_ytdlp_format_options(
    *,
    platform: Platform,
    preset: Preset | None,
    format_id: str | None,
    audio_format: str | None = None,
) -> dict[str, Any]:
    """
    Build yt-dlp format selector and postprocessor options.
    Guarantees stream copy (-c copy) whenever merging compatible video+audio,
    preferring MP4 (H.264/AAC) for 'compatible' and allowing MKV/WebM for max quality 4K VP9/AV1.
    """
    # Override preset if explicit audio_format passed
    effective_preset = preset or Preset.BEST
    if audio_format == "m4a":
        effective_preset = Preset.AUDIO_M4A
    elif audio_format == "mp3_192":
        effective_preset = Preset.AUDIO_MP3_192
    elif audio_format == "mp3_320":
        effective_preset = Preset.AUDIO_MP3_320

    # Explicit format_id chosen from Advanced list
    if format_id:
        # Validate format_id contains only safe characters (no injection/expression abuse)
        clean_id = "".join(ch for ch in format_id if ch.isalnum() or ch in "+_-/.")
        # If user picks a video-only format ID (no '+'), pair with bestaudio fallback cleanly
        selector = clean_id if "+" in clean_id else f"{clean_id}+bestaudio/{clean_id}"
        return {
            "format": selector,
            "merge_output_format": "mkv/mp4",
            "postprocessors": [],
        }

    if effective_preset == Preset.AUDIO_M4A:
        return {
            "format": "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "0",
                }
            ],
        }

    if effective_preset in {Preset.AUDIO_MP3_192, Preset.AUDIO_MP3_320}:
        bitrate = "320" if effective_preset == Preset.AUDIO_MP3_320 else "192"
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }
            ],
        }

    if effective_preset == Preset.COMPATIBLE:
        return {
            "format": (
                "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
                "best[ext=mp4]/bestvideo+bestaudio/best"
            ),
            "merge_output_format": "mp4",
            "postprocessors": [],
        }

    if effective_preset == Preset.BEST:
        if platform == Platform.X:
            # X/Twitter: pick highest-bitrate MP4 variant
            return {
                "format": "bestvideo*+bestaudio/best[ext=mp4]/best",
                "format_sort": ["tbr", "res", "fps", "ext:mp4:m4a"],
                "merge_output_format": "mp4",
                "postprocessors": [],
            }
        # Max quality: allow VP9/AV1 4K in MKV/WebM or MP4 without re-encoding
        return {
            "format": "bestvideo*+bestaudio/best",
            "format_sort": ["res", "fps", "hdr:12", "vcodec:av01:vp9.2:vp9:h264", "tbr"],
            "merge_output_format": "mkv/mp4",
            "postprocessors": [],
        }

    height_caps = {
        Preset.P2160: 2160,
        Preset.P1440: 1440,
        Preset.P1080: 1080,
        Preset.P720: 720,
        Preset.P480: 480,
    }
    cap = height_caps.get(effective_preset, 1080)
    merge_fmt = "mkv/mp4" if cap >= 1440 else "mp4"
    return {
        "format": (f"bestvideo*[height<={cap}]+bestaudio/best[height<={cap}]/bestvideo*+bestaudio/best"),
        "merge_output_format": merge_fmt,
        "postprocessors": [],
    }
