"""Filename sanitization and RFC 5987 Content-Disposition header builder."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_FORBIDDEN_CHARS_RE = re.compile(r'[<>:"/\\|?*]+')
_WHITESPACE_RE = re.compile(r"\s+")
_WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


def sanitize_filename(name: str, ext: str | None = None, max_stem_length: int = 120) -> str:
    """
    Sanitize a video title into a safe cross-platform UTF-8 filename:
    - Normalizes Unicode (NFC)
    - Strips path separators, null bytes, control chars, and OS-forbidden chars
    - Prevents hidden files or Windows reserved device names
    - Bounds total stem length
    """
    cleaned = unicodedata.normalize("NFC", name or "")
    cleaned = _CONTROL_CHARS_RE.sub("", cleaned)
    cleaned = cleaned.replace("/", " ").replace("\\", " ")
    cleaned = _FORBIDDEN_CHARS_RE.sub(" ", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip(" ._-")

    if not cleaned:
        cleaned = "video"

    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"

    if len(cleaned) > max_stem_length:
        cleaned = cleaned[:max_stem_length].rstrip(" ._-") or "video"

    if ext:
        clean_ext = re.sub(r"[^a-zA-Z0-9]", "", ext.lstrip(".")).lower() or "mp4"
        return f"{cleaned}.{clean_ext}"
    return cleaned


def build_content_disposition(filename: str) -> str:
    """
    Build a standards-compliant RFC 5987 Content-Disposition header with both
    ASCII fallback `filename="..."` and UTF-8 `filename*=UTF-8''...`.
    """
    safe_utf8 = (
        sanitize_filename(filename.rsplit(".", 1)[0], filename.rsplit(".", 1)[1])
        if "." in filename
        else sanitize_filename(filename)
    )

    # ASCII fallback
    ascii_fallback = (
        unicodedata.normalize("NFKD", safe_utf8)
        .encode("ascii", "ignore")
        .decode("ascii")
        .replace('"', "")
        .strip(" ._-")
    )
    if not ascii_fallback or ascii_fallback.startswith("."):
        ext = safe_utf8.rsplit(".", 1)[1] if "." in safe_utf8 else "mp4"
        ascii_fallback = f"download.{ext}"

    utf8_encoded = quote(safe_utf8, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_encoded}"
