"""Storage management: disk-quota guard, atomic moves, MIME types, Range parsing, TTL cleanup."""

from __future__ import annotations

import logging
import mimetypes
import os
import shutil
import time
from pathlib import Path

from app.errors import AppError, ErrorCode
from app.metrics import DISK_FREE_BYTES

logger = logging.getLogger(__name__)

_EXTRA_MIMES: dict[str, str] = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".opus": "audio/opus",
    ".ogg": "audio/ogg",
    ".srt": "application/x-subrip; charset=utf-8",
    ".vtt": "text/vtt; charset=utf-8",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class StorageManager:
    def __init__(
        self,
        storage_dir: Path,
        tmp_dir: Path,
        *,
        min_free_disk_bytes: int = 1_073_741_824,
        file_ttl_seconds: int = 1800,
    ) -> None:
        self.storage_dir = storage_dir
        self.tmp_dir = tmp_dir
        self.min_free_disk_bytes = min_free_disk_bytes
        self.file_ttl_seconds = file_ttl_seconds
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def free_bytes(self) -> int:
        usage = shutil.disk_usage(self.storage_dir)
        DISK_FREE_BYTES.set(usage.free)
        return int(usage.free)

    def has_sufficient_space(self) -> bool:
        return self.free_bytes() >= self.min_free_disk_bytes

    def assert_disk_quota(self) -> None:
        free = self.free_bytes()
        if free < self.min_free_disk_bytes:
            raise AppError(
                code=ErrorCode.DISK_FULL,
                message="Temporary server storage is currently full.",
                hint="Please retry in a few minutes after older temporary downloads expire.",
                retryable=True,
                status_code=507,
            )

    def job_work_dir(self, job_id: str) -> Path:
        path = self.tmp_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def job_final_dir(self, job_id: str) -> Path:
        path = self.storage_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def move_atomically(self, src: Path, dst_dir: Path, final_name: str) -> Path:
        """
        Atomically move a completed temp file into the final storage directory.
        Falls back to copy+replace when tmp_dir (tmpfs) and storage_dir are on different mounts.
        """
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / final_name
        tmp_dst = dst_dir / f".{final_name}.tmp"
        try:
            os.replace(src, dst)
            return dst
        except OSError:
            shutil.copy2(src, tmp_dst)
            os.replace(tmp_dst, dst)
            src.unlink(missing_ok=True)
            return dst

    def cleanup_job(self, job_id: str) -> None:
        for base in (self.tmp_dir / job_id, self.storage_dir / job_id):
            if base.exists():
                shutil.rmtree(base, ignore_errors=True)

    def cleanup_expired(self, now: float | None = None) -> int:
        """Delete job directories older than file_ttl_seconds from storage and stale tmp dirs."""
        current = now if now is not None else time.time()
        removed = 0
        for root, ttl in ((self.storage_dir, self.file_ttl_seconds), (self.tmp_dir, self.file_ttl_seconds)):
            if not root.exists():
                continue
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                try:
                    mtime = child.stat().st_mtime
                except OSError:
                    continue
                if current - mtime > ttl:
                    shutil.rmtree(child, ignore_errors=True)
                    removed += 1
        if removed:
            logger.info("Cleaned up %d expired download directories", removed)
        self.free_bytes()
        return removed

    @staticmethod
    def guess_mime(path: Path) -> str:
        ext = path.suffix.lower()
        if ext in _EXTRA_MIMES:
            return _EXTRA_MIMES[ext]
        guessed, _ = mimetypes.guess_type(str(path))
        return guessed or "application/octet-stream"


def parse_range_header(range_header: str, file_size: int) -> tuple[int, int] | None:
    """
    Parse a single HTTP Range header (`bytes=start-end`, `bytes=start-`, `bytes=-suffix`).
    Returns (start, end) inclusive, or None if invalid/unsatisfiable.
    """
    if not range_header or not range_header.lower().startswith("bytes="):
        return None
    spec = range_header[6:].strip()
    if "," in spec:
        # Multi-range requests: serve first range cleanly
        spec = spec.split(",", 1)[0].strip()
    if "-" not in spec:
        return None

    start_s, end_s = spec.split("-", 1)
    try:
        if start_s == "":
            suffix = int(end_s)
            if suffix <= 0:
                return None
            start = max(0, file_size - suffix)
            end = file_size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else file_size - 1
    except ValueError:
        return None

    if start < 0 or start >= file_size or end < start:
        return None
    end = min(end, file_size - 1)
    return start, end
