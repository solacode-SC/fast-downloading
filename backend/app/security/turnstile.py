"""Optional Cloudflare Turnstile verification on job creation."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings
from app.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(
    token: str | None,
    remote_ip: str | None,
    settings: Settings,
) -> None:
    """Verify Cloudflare Turnstile token when enabled via TURNSTILE_ENABLED=true."""
    if not settings.turnstile_enabled:
        return

    secret = settings.turnstile_secret_key.get_secret_value().strip()
    if not secret:
        logger.warning("Turnstile enabled but TURNSTILE_SECRET_KEY is empty; skipping verification")
        return

    if not token:
        raise AppError(
            code=ErrorCode.TURNSTILE_FAILED,
            message="Human verification is required before starting a download.",
            hint="Complete the verification challenge and try again.",
            retryable=True,
            status_code=403,
        )

    payload: dict[str, str] = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=payload)
            data = resp.json()
    except Exception as exc:
        logger.warning("Turnstile verification request failed: %s", exc)
        raise AppError(
            code=ErrorCode.TURNSTILE_FAILED,
            message="Could not verify anti-bot challenge.",
            hint="Please retry in a moment.",
            retryable=True,
            status_code=503,
        ) from exc

    if not data.get("success"):
        raise AppError(
            code=ErrorCode.TURNSTILE_FAILED,
            message="Verification challenge failed or expired.",
            hint="Refresh the verification widget and try again.",
            retryable=True,
            status_code=403,
        )
