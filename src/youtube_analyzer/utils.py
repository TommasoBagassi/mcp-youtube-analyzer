# src/youtube_analyzer/utils.py
"""Shared utilities: URL parsing, auth config, image encoding."""

import base64
import io
import os
import re

from PIL import Image as PILImage


def parse_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats.

    Supports: youtube.com/watch?v=, youtu.be/, youtube.com/shorts/,
    youtube.com/embed/, and bare 11-character video IDs.
    """
    if not url:
        raise ValueError("Could not parse YouTube video ID from empty string")

    patterns = [
        r"(?:youtube\.com/watch\?.*?v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError(f"Could not parse YouTube video ID from: {url}")


_TIMESTAMP_RE = re.compile(r"\[(\d+:\d+:\d+|\d+:\d+)\]")


def extract_timestamp_seconds(line: str) -> int | None:
    """Extract timestamp in seconds from a line like '[1:30] text'."""
    match = _TIMESTAMP_RE.match(line)
    if not match:
        return None
    parts = match.group(1).split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return int(parts[0]) * 60 + int(parts[1])


def format_timestamp(seconds: float) -> str:
    """Format seconds as [M:SS] or [H:MM:SS]."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"[{hours}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes}:{secs:02d}]"


def get_yt_dlp_cookie_opts() -> dict:
    """Build yt-dlp cookie options from environment variables.

    YOUTUBE_COOKIE_SOURCE (e.g. 'firefox') takes precedence over
    YOUTUBE_COOKIES_FILE (path to cookies.txt).
    """
    cookie_source = os.environ.get("YOUTUBE_COOKIE_SOURCE")
    cookies_file = os.environ.get("YOUTUBE_COOKIES_FILE")

    if cookie_source:
        return {"cookiesfrombrowser": (cookie_source,)}
    if cookies_file:
        if not os.path.isfile(cookies_file):
            raise FileNotFoundError(f"Cookies file not found: {cookies_file}")
        return {"cookiefile": cookies_file}
    return {}


def get_max_duration() -> int:
    """Get maximum allowed video duration in seconds from env."""
    return int(os.environ.get("YOUTUBE_MAX_DURATION", "10800"))


def encode_image_base64(image: PILImage.Image, quality: int = 60) -> str:
    """Encode a PIL Image as a base64 JPEG string."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
