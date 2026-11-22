"""Pydantic v2 API schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Platform(StrEnum):
    YOUTUBE = "youtube"
    X = "x"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class Preset(StrEnum):
    BEST = "best"
    COMPATIBLE = "compatible"
    P2160 = "2160p"
    P1440 = "1440p"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"
    AUDIO_M4A = "audio_m4a"
    AUDIO_MP3_320 = "audio_mp3_320"
    AUDIO_MP3_192 = "audio_mp3_192"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RESOLVING = "resolving"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorDetail(BaseModel):
    code: str
    message: str
    hint: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorDetail


class SubtitleTrack(BaseModel):
    lang: str
    name: str
    ext: str = "srt"
    auto: bool = False


class FormatItem(BaseModel):
    format_id: str
    ext: str
    resolution: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    is_hdr: bool = False
    is_audio_only: bool = False
    is_video_only: bool = False
    is_progressive: bool = False
    tbr_kbps: float | None = None
    abr_kbps: float | None = None
    filesize_bytes: int | None = None
    filesize_approx_bytes: int | None = None
    note: str | None = None
    compatible: bool = False


class PresetOption(BaseModel):
    id: Preset
    label: str
    description: str
    estimated_ext: str
    estimated_height: int | None = None
    estimated_size_bytes: int | None = None
    available: bool = True


class MediaEntrySummary(BaseModel):
    index: int
    id: str
    title: str
    url: str
    duration_seconds: int | None = None
    thumbnail_url: str | None = None


class ResolveRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)


class ResolveResponse(BaseModel):
    url: str
    normalized_url: str
    platform: Platform
    id: str
    title: str
    uploader: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None
    is_playlist: bool = False
    is_carousel: bool = False
    entries: list[MediaEntrySummary] = Field(default_factory=list)
    presets: list[PresetOption] = Field(default_factory=list)
    formats: list[FormatItem] = Field(default_factory=list)
    subtitles: list[SubtitleTrack] = Field(default_factory=list)
    cached: bool = False
    resolve_ms: int = 0


class CreateJobRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)
    preset: Preset | None = Preset.BEST
    format_id: str | None = Field(default=None, max_length=128)
    audio_format: Literal["m4a", "mp3_192", "mp3_320"] | None = None
    subtitle_lang: str | None = Field(default=None, max_length=32)
    download_thumbnail: bool = False
    playlist_item: int | None = Field(default=None, ge=1, le=50)
    turnstile_token: str | None = Field(default=None, max_length=2048)


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    reused: bool = False


class JobSnapshot(BaseModel):
    job_id: str
    platform: Platform
    url: str
    title: str | None = None
    thumbnail_url: str | None = None
    status: JobStatus
    progress_percent: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    speed_bytes_per_sec: float | None = None
    eta_seconds: int | None = None
    phase_detail: str | None = None
    download_token: str | None = None
    download_url: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    filesize_bytes: int | None = None
    subtitle_token: str | None = None
    subtitle_url: str | None = None
    thumbnail_token: str | None = None
    thumbnail_url_download: str | None = None
    error: ErrorDetail | None = None
    created_at: float
    updated_at: float
    expires_at: float | None = None


class VersionResponse(BaseModel):
    app_version: str
    ytdlp_version: str
    ffmpeg_version: str
    aria2c_available: bool
    curl_cffi_available: bool
    pot_provider_enabled: bool


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded", "not_ready"]
    redis: bool
    ffmpeg: bool
    ytdlp_version: str
    pot_provider: bool | None = None
    disk_free_bytes: int
    disk_ok: bool
    cookies: dict[str, str]
    proxies_healthy: int
    details: dict[str, Any] = Field(default_factory=dict)
