# src/youtube_analyzer/video_info.py
"""Video metadata fetching via yt-dlp."""

import logging

import yt_dlp
from yt_dlp.utils import DownloadError

from .utils import get_max_duration, get_yt_dlp_cookie_opts, parse_video_id

logger = logging.getLogger(__name__)


def fetch_video_info(url: str) -> dict:
    """Fetch video metadata without downloading."""
    video_id = parse_video_id(url)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        **get_yt_dlp_cookie_opts(),
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
    except DownloadError as e:
        error_msg = str(e).lower()
        if "private" in error_msg or "sign in" in error_msg or "login" in error_msg:
            if not get_yt_dlp_cookie_opts():
                raise ValueError(
                    "Video is private. Set YOUTUBE_COOKIE_SOURCE or YOUTUBE_COOKIES_FILE"
                ) from e
        raise

    if info is None:
        raise RuntimeError("yt-dlp returned no metadata for this video")

    duration = info.get("duration", 0)
    max_dur = get_max_duration()
    if duration > max_dur:
        hours = duration / 3600
        max_hours = max_dur / 3600
        raise ValueError(
            f"Video is {hours:.1f} hours. "
            f"Max is {max_hours:.1f} hours. "
            f"Set YOUTUBE_MAX_DURATION to override"
        )

    subtitles = list(info.get("subtitles", {}).keys())
    auto_captions = list(info.get("automatic_captions", {}).keys())
    all_langs = sorted(set(subtitles + auto_captions))

    return {
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "duration": duration,
        "upload_date": info.get("upload_date"),
        "description": info.get("description"),
        "view_count": info.get("view_count"),
        "subtitle_languages": all_langs,
    }
