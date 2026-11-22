"""Anti-Block L4: Optional per-platform Netscape cookie manager with hot-reload and expiry tracking."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from app.metrics import COOKIE_STATUS
from app.schemas import Platform

logger = logging.getLogger(__name__)


@dataclass
class CookieState:
    path: Path
    mtime: float = 0.0
    valid_format: bool = False
    expired: bool = False
    last_checked: float = 0.0


class CookieManager:
    """
    Loads user-supplied Netscape cookies from `/run/secrets/cookies/{platform}.txt`.
    - Hot-reloads automatically when file mtime changes (no container restart needed).
    - Tracks authentication failures so `/readyz` clearly marks expired cookies.
    - Never logs cookie file contents.
    """

    def __init__(self, cookies_dir: Path) -> None:
        self._dir = cookies_dir
        self._states: dict[Platform, CookieState] = {
            p: CookieState(path=cookies_dir / f"{p.value}.txt") for p in Platform
        }
        self.refresh_all()

    @staticmethod
    def _safe_is_file(path: Path) -> bool:
        try:
            return path.is_file()
        except OSError:
            return False

    @staticmethod
    def validate_netscape_file(path: Path) -> bool:
        try:
            if not path.is_file():
                return False
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        if not lines:
            return False
        # Must contain at least one 7-column tab-separated Netscape cookie entry
        for ln in lines:
            if ln.startswith("#") and not ln.startswith("#HttpOnly_"):
                continue
            parts = ln.split("\t")
            if len(parts) >= 7:
                return True
        return False

    def _refresh_platform(self, platform: Platform) -> CookieState:
        state = self._states[platform]
        state.last_checked = time.time()
        if not self._safe_is_file(state.path):
            state.mtime = 0.0
            state.valid_format = False
            state.expired = False
            COOKIE_STATUS.labels(platform=platform.value).set(-1)
            return state

        try:
            current_mtime = state.path.stat().st_mtime
        except OSError:
            state.valid_format = False
            COOKIE_STATUS.labels(platform=platform.value).set(0)
            return state

        # Hot-reload if modified since last check
        if current_mtime != state.mtime:
            state.mtime = current_mtime
            state.valid_format = self.validate_netscape_file(state.path)
            state.expired = False  # Freshly updated file clears previous expiry flag
            logger.info(
                "Hot-reloaded cookies file for platform=%s valid=%s",
                platform.value,
                state.valid_format,
                extra={"platform": platform.value},
            )

        metric_val = 1 if (state.valid_format and not state.expired) else 0
        COOKIE_STATUS.labels(platform=platform.value).set(metric_val)
        return state

    def refresh_all(self) -> None:
        for p in Platform:
            self._refresh_platform(p)

    def get_cookie_path(self, platform: Platform) -> str | None:
        """Return cookie file path if present, validly formatted, and not marked expired."""
        state = self._refresh_platform(platform)
        if state.valid_format and not state.expired:
            return str(state.path)
        return None

    def mark_expired(self, platform: Platform) -> None:
        state = self._states[platform]
        if self._safe_is_file(state.path):
            state.expired = True
            COOKIE_STATUS.labels(platform=platform.value).set(0)
            logger.warning(
                "Marked cookies as expired after auth failure",
                extra={"platform": platform.value},
            )

    def status_summary(self) -> dict[str, str]:
        """Return status per platform for /readyz without leaking any cookie data."""
        summary: dict[str, str] = {}
        for p in Platform:
            state = self._refresh_platform(p)
            if not self._safe_is_file(state.path):
                summary[p.value] = "not_configured"
            elif not state.valid_format:
                summary[p.value] = "invalid_format"
            elif state.expired:
                summary[p.value] = "expired"
            else:
                summary[p.value] = "valid"
        return summary
