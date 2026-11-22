"""Anti-Block L1: Runtime yt-dlp auto-updater with self-test and atomic rollback."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from typing import Any

import yt_dlp

from app.config import Settings

logger = logging.getLogger(__name__)


def current_ytdlp_version() -> str:
    return str(getattr(yt_dlp.version, "__version__", "unknown"))


def ffmpeg_version() -> str:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return "unavailable"
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            first_line = proc.stdout.splitlines()[0].strip()
            parts = first_line.split()
            return parts[2] if len(parts) >= 3 else first_line
    except Exception as exc:
        logger.debug("ffmpeg version check failed: %s", exc)
    return "unavailable"


def update_ytdlp_with_rollback(settings: Settings) -> dict[str, Any]:
    """
    Update yt-dlp into a dedicated writable overlay directory (compatible with read_only rootfs):
    - Respects YTDLP_PINNED_VERSION if set.
    - Supports YTDLP_CHANNEL=nightly (--pre yt-dlp[default]) or stable.
    - Runs an isolated subprocess self-test importing yt_dlp and checking extractors.
    - Automatically rolls back to the previous overlay if the self-test fails.
    """
    before_version = current_ytdlp_version()
    overlay_dir = settings.ytdlp_overlay_dir
    staging_dir = overlay_dir.parent / f"{overlay_dir.name}.staging"
    backup_dir = overlay_dir.parent / f"{overlay_dir.name}.backup"

    try:
        overlay_dir.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create yt-dlp overlay directory %s: %s", overlay_dir, exc)
        return {
            "updated": False,
            "before_version": before_version,
            "after_version": before_version,
            "reason": f"overlay_unwritable: {exc}",
        }

    pkg_spec = "yt-dlp"
    pip_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "--no-deps",
        "--upgrade",
        "--target",
        str(staging_dir),
    ]
    if settings.ytdlp_pinned_version:
        pkg_spec = f"yt-dlp=={settings.ytdlp_pinned_version}"
    elif settings.ytdlp_channel == "nightly":
        pip_cmd.append("--pre")
    pip_cmd.append(pkg_spec)

    shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Running yt-dlp update: spec=%s channel=%s", pkg_spec, settings.ytdlp_channel)
    proc = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0:
        shutil.rmtree(staging_dir, ignore_errors=True)
        logger.error("yt-dlp pip update failed: %s", proc.stderr[-500:])
        return {
            "updated": False,
            "before_version": before_version,
            "after_version": before_version,
            "reason": "pip_install_failed",
        }

    # Self-test the staged yt-dlp in a clean child process before activating
    test_env = os.environ.copy()
    existing_pp = test_env.get("PYTHONPATH", "")
    test_env["PYTHONPATH"] = f"{staging_dir}:{existing_pp}" if existing_pp else str(staging_dir)

    selftest_code = (
        "import yt_dlp; "
        "from yt_dlp.extractor import get_info_extractor; "
        "assert get_info_extractor('Youtube') is not None; "
        "assert get_info_extractor('Twitter') is not None; "
        "assert get_info_extractor('Instagram') is not None; "
        "assert get_info_extractor('Facebook') is not None; "
        "print(yt_dlp.version.__version__)"
    )
    test_proc = subprocess.run(
        [sys.executable, "-c", selftest_code],
        env=test_env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if test_proc.returncode != 0:
        shutil.rmtree(staging_dir, ignore_errors=True)
        logger.error(
            "yt-dlp post-update self-test failed; keeping version %s: %s",
            before_version,
            test_proc.stderr[-500:],
        )
        return {
            "updated": False,
            "rolled_back": True,
            "before_version": before_version,
            "after_version": before_version,
            "reason": "selftest_failed",
        }

    new_version = test_proc.stdout.strip().splitlines()[-1] if test_proc.stdout.strip() else "unknown"

    # Atomic swap with backup rollback capability
    shutil.rmtree(backup_dir, ignore_errors=True)
    if overlay_dir.exists():
        overlay_dir.rename(backup_dir)
    try:
        staging_dir.rename(overlay_dir)
        shutil.rmtree(backup_dir, ignore_errors=True)
    except OSError as exc:
        logger.error("Failed swapping yt-dlp overlay; restoring backup: %s", exc)
        if backup_dir.exists() and not overlay_dir.exists():
            backup_dir.rename(overlay_dir)
        shutil.rmtree(staging_dir, ignore_errors=True)
        return {
            "updated": False,
            "rolled_back": True,
            "before_version": before_version,
            "after_version": before_version,
            "reason": f"swap_failed: {exc}",
        }

    logger.info("yt-dlp updated successfully: %s -> %s", before_version, new_version)
    return {
        "updated": True,
        "before_version": before_version,
        "after_version": new_version,
    }


def main() -> int:
    from app.config import get_settings
    from app.logging_setup import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)
    result = update_ytdlp_with_rollback(settings)
    print(result)
    return 0 if result.get("updated") or result.get("reason") == "overlay_unwritable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
