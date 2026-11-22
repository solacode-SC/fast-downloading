"""Shared FastAPI request helpers and dependency extraction."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from app.config import Settings


def get_client_ip(request: Request, settings: Settings) -> str:
    """Extract client IP safely (respecting X-Forwarded-For only when behind trusted Nginx)."""
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",", 1)[0].strip()
            if first:
                return first
        xri = request.headers.get("x-real-ip")
        if xri:
            return xri.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def get_app_state(request: Request) -> Any:
    return request.app.state.services
