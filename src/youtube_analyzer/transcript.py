# src/youtube_analyzer/transcript.py
"""Transcript extraction with fallback chain.

Fallback order:
1. youtube-transcript-api (public videos, fast)
2. yt-dlp subtitle extraction (auth-aware)
3. faster-whisper (optional, local transcription)
"""

import logging
import re

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from .utils import format_timestamp, get_yt_dlp_cookie_opts, parse_video_id
from .video_info import fetch_video_info

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50_000

_transcript_cache: dict[tuple, tuple] = {}


def fetch_transcript(
    url: str,
    lang: str = "en",
    include_timestamps: bool = True,
    cursor: str | None = None,
) -> dict:
    """Fetch transcript using the fallback chain.

    Returns a dict with keys: text, source, next_cursor, total_length, position,
    title, duration, lang.
    """
    video_id = parse_video_id(url)
    cache_key = (video_id, lang, include_timestamps)

    if cache_key in _transcript_cache:
        transcript_text, source, title, duration = _transcript_cache[cache_key]
    else:
        info = fetch_video_info(url)
        title = info["title"]
        duration = info["duration"]

        transcript_text = None
        source = None

        # 1. Try youtube-transcript-api
        try:
            transcript_text = _fetch_via_transcript_api(video_id, lang, include_timestamps)
            source = "captions"
        except Exception as e:
            logger.debug("youtube-transcript-api failed: %s", e)

        # 2. Try yt-dlp subtitles
        if transcript_text is None:
            try:
                transcript_text = _fetch_via_ytdlp(video_id, lang, include_timestamps)
                source = "yt-dlp-subtitles"
            except Exception as e:
                logger.debug("yt-dlp subtitles failed: %s", e)

        # 3. Try whisper fallback
        if transcript_text is None:
            try:
                import faster_whisper  # noqa: F401
            except ImportError:
                raise RuntimeError(
                    "No captions available. Install faster-whisper: `uv sync --extra whisper`"
                )
            from .whisper import transcribe_video
            transcript_text = transcribe_video(video_id, include_timestamps)
            source = "whisper"

        _transcript_cache[cache_key] = (transcript_text, source, title, duration)

    # Pagination (same as before)
    offset = int(cursor) if cursor else 0
    end = offset + CHUNK_SIZE
    chunk = transcript_text[offset:end]

    if end < len(transcript_text):
        last_period = chunk.rfind(". ")
        if last_period > CHUNK_SIZE // 2:
            chunk = chunk[: last_period + 2]
            end = offset + len(chunk)

    next_cursor = str(end) if end < len(transcript_text) else None

    return {
        "text": chunk,
        "source": source,
        "next_cursor": next_cursor,
        "total_length": len(transcript_text),
        "position": offset,
        "title": title,
        "duration": duration,
        "lang": lang,
    }


def _fetch_via_transcript_api(
    video_id: str, lang: str, include_timestamps: bool
) -> str:
    """Fetch transcript using youtube-transcript-api (v1.2+ instance API)."""
    ytt_api = YouTubeTranscriptApi()
    fetched = ytt_api.fetch(video_id, languages=[lang])
    entries = [
        {"text": snippet.text, "start": snippet.start, "duration": snippet.duration}
        for snippet in fetched
    ]
    return _format_entries(entries, include_timestamps)


def _fetch_via_ytdlp(video_id: str, lang: str, include_timestamps: bool) -> str:
    """Fetch subtitles using yt-dlp (auth-aware). Single-call approach."""
    import glob
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [lang],
            "subtitlesformat": "vtt",
            "outtmpl": f"{tmpdir}/%(id)s.%(ext)s",
            **get_yt_dlp_cookie_opts(),
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
        if not vtt_files:
            raise ValueError(f"No subtitles found for language: {lang}")

        return _parse_vtt(vtt_files[0], include_timestamps)


def _format_entries(
    entries: list[dict], include_timestamps: bool
) -> str:
    """Format transcript entries into text."""
    lines = []
    for entry in entries:
        text = entry["text"].strip()
        if not text:
            continue
        if include_timestamps:
            ts = format_timestamp(entry["start"])
            lines.append(f"{ts} {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _parse_vtt(filepath: str, include_timestamps: bool) -> str:
    """Parse a WebVTT subtitle file into plain text.

    Handles both HH:MM:SS.mmm and MM:SS.mmm timestamp formats.
    Deduplicates repeated lines common in auto-generated captions.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = []
    prev_text = None
    in_cue = False
    current_start = 0.0
    for line in content.split("\n"):
        line = line.strip()
        if "-->" in line:
            ts_match = re.match(r"(?:(\d+):)?(\d+):(\d+)\.(\d+)", line)
            if ts_match:
                h = int(ts_match.group(1) or 0)
                m, s = int(ts_match.group(2)), int(ts_match.group(3))
                ms = int(ts_match.group(4).ljust(3, '0')[:3])
                current_start = h * 3600 + m * 60 + s + ms / 1000
            in_cue = True
        elif in_cue and line:
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean and clean != prev_text:
                prev_text = clean
                if include_timestamps:
                    lines.append(f"{format_timestamp(current_start)} {clean}")
                else:
                    lines.append(clean)
        elif not line:
            in_cue = False

    return "\n".join(lines)
