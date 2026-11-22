"""Redis-backed Job Store, Idempotency Index, Resolve Cache, and Pub/Sub event broadcaster."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.schemas import JobSnapshot, JobStatus, Platform, ResolveResponse


def make_idempotency_key(
    *,
    normalized_url: str,
    preset: str | None,
    format_id: str | None,
    audio_format: str | None,
    subtitle_lang: str | None,
    download_thumbnail: bool,
    playlist_item: int | None,
) -> str:
    raw = json.dumps(
        {
            "u": normalized_url,
            "p": preset,
            "f": format_id,
            "a": audio_format,
            "s": subtitle_lang,
            "t": download_thumbnail,
            "i": playlist_item,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"vdl:idem:{digest}"


def make_resolve_cache_key(normalized_url: str) -> str:
    digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:32]
    return f"vdl:resolve:{digest}"


class JobStore:
    def __init__(self, redis_client: Any, *, file_ttl_seconds: int = 1800) -> None:
        self._redis = redis_client
        self._file_ttl = file_ttl_seconds

    @staticmethod
    def job_key(job_id: str) -> str:
        return f"vdl:job:{job_id}"

    @staticmethod
    def cancel_key(job_id: str) -> str:
        return f"vdl:job:cancel:{job_id}"

    @staticmethod
    def event_channel(job_id: str) -> str:
        return f"vdl:job:events:{job_id}"

    @staticmethod
    def artifact_key(job_id: str) -> str:
        return f"vdl:files:{job_id}"

    async def get_cached_resolve(self, normalized_url: str) -> ResolveResponse | None:
        raw = await self._redis.get(make_resolve_cache_key(normalized_url))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            resp = ResolveResponse.model_validate(data)
            resp.cached = True
            return resp
        except Exception:
            return None

    async def set_cached_resolve(self, normalized_url: str, response: ResolveResponse, ttl_seconds: int) -> None:
        await self._redis.set(
            make_resolve_cache_key(normalized_url),
            response.model_dump_json(),
            ex=max(30, ttl_seconds),
        )

    async def get_job(self, job_id: str) -> JobSnapshot | None:
        raw = await self._redis.get(self.job_key(job_id))
        if not raw:
            return None
        return JobSnapshot.model_validate_json(raw)

    async def save_job(self, snapshot: JobSnapshot, *, publish: bool = True) -> None:
        snapshot.updated_at = time.time()
        payload = snapshot.model_dump_json()
        ttl = max(3600, self._file_ttl + 600)
        await self._redis.set(self.job_key(snapshot.job_id), payload, ex=ttl)
        if publish:
            await self._redis.publish(self.event_channel(snapshot.job_id), payload)

    async def find_idempotent_job(self, idem_key: str) -> JobSnapshot | None:
        existing_id = await self._redis.get(idem_key)
        if not existing_id:
            return None
        job_id = existing_id.decode("utf-8") if isinstance(existing_id, bytes) else str(existing_id)
        snap = await self.get_job(job_id)
        if snap is None:
            await self._redis.delete(idem_key)
            return None
        if snap.status in {
            JobStatus.QUEUED,
            JobStatus.RESOLVING,
            JobStatus.DOWNLOADING,
            JobStatus.MERGING,
            JobStatus.READY,
        }:
            # Check if READY job file hasn't expired
            if snap.status == JobStatus.READY and snap.expires_at and time.time() >= snap.expires_at:
                await self._redis.delete(idem_key)
                return None
            return snap
        return None

    async def bind_idempotent_job(self, idem_key: str, job_id: str) -> None:
        await self._redis.set(idem_key, job_id, ex=self._file_ttl)

    async def clear_idempotent_job(self, idem_key: str) -> None:
        await self._redis.delete(idem_key)

    async def request_cancel(self, job_id: str) -> None:
        await self._redis.set(self.cancel_key(job_id), "1", ex=3600)

    async def is_cancelled(self, job_id: str) -> bool:
        val = await self._redis.get(self.cancel_key(job_id))
        return bool(val)

    async def save_artifact_metadata(
        self,
        job_id: str,
        *,
        platform: Platform,
        media_path: str,
        media_filename: str,
        media_mime: str,
        media_size: int,
        subtitle_path: str | None = None,
        subtitle_filename: str | None = None,
        thumbnail_path: str | None = None,
        thumbnail_filename: str | None = None,
        expires_at: float,
    ) -> None:
        meta = {
            "platform": platform.value,
            "media": {
                "path": media_path,
                "filename": media_filename,
                "mime": media_mime,
                "size": media_size,
            },
            "subtitle": (
                {"path": subtitle_path, "filename": subtitle_filename, "mime": "application/x-subrip; charset=utf-8"}
                if subtitle_path
                else None
            ),
            "thumbnail": (
                {"path": thumbnail_path, "filename": thumbnail_filename, "mime": "image/jpeg"}
                if thumbnail_path
                else None
            ),
            "expires_at": expires_at,
        }
        await self._redis.set(self.artifact_key(job_id), json.dumps(meta), ex=self._file_ttl + 300)

    async def get_artifact_metadata(self, job_id: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self.artifact_key(job_id))
        if not raw:
            return None
        return dict(json.loads(raw))

    async def delete_artifact_metadata(self, job_id: str) -> None:
        await self._redis.delete(self.artifact_key(job_id))
