"""Short-lived HMAC-SHA256 signed download tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.errors import AppError, ErrorCode


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_download_token(
    *,
    job_id: str,
    kind: str,
    secret: str,
    ttl_seconds: int = 900,
    now: float | None = None,
) -> str:
    """Create a URL-safe HMAC-SHA256 signed token bound to job_id, artifact kind, and expiry."""
    issued = int(now if now is not None else time.time())
    payload = {
        "j": job_id,
        "k": kind,  # "media" | "subtitle" | "thumbnail"
        "exp": issued + ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def verify_download_token(
    token: str,
    *,
    secret: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify signature and expiration; return decoded payload dict."""
    parts = token.split(".")
    if len(parts) != 2:
        raise AppError(
            code=ErrorCode.INVALID_TOKEN,
            message="Invalid download link.",
            hint="Request a fresh download from the app.",
            status_code=403,
        )

    payload_b64, sig_b64 = parts
    expected_sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()

    try:
        provided_sig = _b64url_decode(sig_b64)
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise AppError(
            code=ErrorCode.INVALID_TOKEN,
            message="Malformed download token.",
            hint="Request a fresh download from the app.",
            status_code=403,
        ) from exc

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise AppError(
            code=ErrorCode.INVALID_TOKEN,
            message="Download token signature is invalid.",
            hint="Request a fresh download from the app.",
            status_code=403,
        )

    current = int(now if now is not None else time.time())
    exp = int(payload.get("exp", 0))
    if current > exp:
        raise AppError(
            code=ErrorCode.FILE_EXPIRED,
            message="This download link has expired.",
            hint="Links expire after 15 minutes for security. Click download again to generate a new link.",
            retryable=True,
            status_code=410,
        )

    if not isinstance(payload.get("j"), str) or not isinstance(payload.get("k"), str):
        raise AppError(
            code=ErrorCode.INVALID_TOKEN,
            message="Incomplete download token.",
            hint="Request a fresh download.",
            status_code=403,
        )

    return dict(payload)
