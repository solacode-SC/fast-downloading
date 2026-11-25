"""GET /api/v1/files/{token}: Signed streamed download with HTTP Range (206) and RFC 5987 filenames."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_app_state
from app.errors import AppError, ErrorCode
from app.metrics import BYTES_SERVED
from app.security.sanitize import build_content_disposition
from app.security.tokens import verify_download_token
from app.services.storage import parse_range_header

router = APIRouter(prefix="/api/v1", tags=["files"])

_STREAM_CHUNK_SIZE = 524_288  # 512 KiB


async def _file_chunk_iterator(path: Path, start: int, length: int, platform: str) -> AsyncIterator[bytes]:
    remaining = length
    async with aiofiles.open(path, "rb") as f:
        await f.seek(start)
        while remaining > 0:
            chunk = await f.read(min(_STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            BYTES_SERVED.labels(platform=platform).inc(len(chunk))
            yield chunk


def _resolve_and_stat_artifact(raw_path: str, storage_dir: Path) -> tuple[Path, int]:
    resolved_str = os.path.realpath(raw_path)
    storage_root_str = os.path.realpath(str(storage_dir))
    if not resolved_str.startswith(storage_root_str + os.sep):
        raise AppError(
            code=ErrorCode.INVALID_TOKEN,
            message="Invalid artifact path.",
            hint="Request a fresh download.",
            status_code=403,
        )
    if not os.path.isfile(resolved_str):
        raise AppError(
            code=ErrorCode.FILE_EXPIRED,
            message="File is no longer present on disk.",
            hint="Temporary files expire automatically. Start the download again.",
            retryable=True,
            status_code=410,
        )
    return Path(resolved_str), os.path.getsize(resolved_str)


@router.get("/files/{token}")
async def download_file(token: str, request: Request) -> StreamingResponse:
    """Stream completed media, subtitle, or thumbnail via short-lived HMAC-signed token."""
    svc = get_app_state(request)
    settings = svc.settings

    payload = verify_download_token(
        token,
        secret=settings.hmac_secret.get_secret_value(),
    )
    job_id: str = payload["j"]
    kind: str = payload["k"]

    meta = await svc.job_store.get_artifact_metadata(job_id)
    if meta is None:
        raise AppError(
            code=ErrorCode.FILE_EXPIRED,
            message="This file has expired and was removed from temporary storage.",
            hint="Start the download again to generate a fresh file.",
            retryable=True,
            status_code=410,
        )

    if meta.get("expires_at") and time.time() > float(meta["expires_at"]):
        raise AppError(
            code=ErrorCode.FILE_EXPIRED,
            message="This file has expired.",
            hint="Start the download again.",
            retryable=True,
            status_code=410,
        )

    entry = meta.get(kind)
    if not isinstance(entry, dict) or not entry.get("path"):
        raise AppError(
            code=ErrorCode.FILE_EXPIRED,
            message="Requested download artifact is not available.",
            hint="Confirm the selected format included this artifact.",
            status_code=404,
        )

    file_path, file_size = await asyncio.to_thread(_resolve_and_stat_artifact, str(entry["path"]), settings.storage_dir)
    filename = str(entry.get("filename") or file_path.name)
    mime_type = str(entry.get("mime") or svc.storage.guess_mime(file_path))
    platform = str(meta.get("platform") or "unknown")

    base_headers = {
        "Content-Disposition": build_content_disposition(filename),
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "X-Accel-Buffering": "no",
    }

    range_header = request.headers.get("range")
    if range_header:
        parsed_range = parse_range_header(range_header, file_size)
        if parsed_range is None:
            raise AppError(
                code=ErrorCode.INVALID_URL,
                message="Requested byte range is not satisfiable.",
                hint="Retry without a malformed Range header.",
                status_code=416,
            )
        start, end = parsed_range
        content_length = end - start + 1
        headers = {
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
        }
        return StreamingResponse(
            _file_chunk_iterator(file_path, start, content_length, platform),
            status_code=206,
            media_type=mime_type,
            headers=headers,
        )

    headers = {
        **base_headers,
        "Content-Length": str(file_size),
    }
    return StreamingResponse(
        _file_chunk_iterator(file_path, 0, file_size, platform),
        status_code=200,
        media_type=mime_type,
        headers=headers,
    )
