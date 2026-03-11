# src/youtube_analyzer/server.py
"""FastMCP server definition and tool registrations."""

import logging
import sys

import mcp.types as types
from mcp.server.fastmcp import FastMCP

from .frames import extract_frames_from_video
from .transcript import fetch_transcript as _fetch_transcript
from .utils import extract_timestamp_seconds, format_timestamp
from .video_info import fetch_video_info

logger = logging.getLogger(__name__)

mcp = FastMCP("YouTube Analyzer")


@mcp.tool()
def get_video_info(url: str) -> str:
    """Get metadata for a YouTube video (title, channel, duration, etc.) without downloading it.

    Args:
        url: YouTube video URL or video ID
    """
    info = fetch_video_info(url)
    lines = [
        f"Title: {info['title'] or 'N/A'}",
        f"Channel: {info['channel'] or 'N/A'}",
        f"Duration: {info['duration']}s",
        f"Upload Date: {info['upload_date'] or 'N/A'}",
        f"Views: {info['view_count'] if info['view_count'] is not None else 'N/A'}",
        f"Subtitle Languages: {', '.join(info['subtitle_languages']) or 'None'}",
        "",
        f"Description: {info['description'][:500] if info['description'] else 'N/A'}",
    ]
    return "\n".join(lines)


@mcp.tool()
def get_transcript(
    url: str,
    lang: str = "en",
    include_timestamps: bool = True,
    cursor: str | None = None,
) -> str:
    """Get the transcript/subtitles for a YouTube video.

    Falls back through: captions -> yt-dlp subtitles -> Whisper transcription.
    For long transcripts, use the returned next_cursor to paginate.

    Args:
        url: YouTube video URL or video ID
        lang: Preferred language code (default: en)
        include_timestamps: Include [MM:SS] timestamps (default: true)
        cursor: Pagination cursor from a previous response
    """
    result = _fetch_transcript(url, lang=lang, include_timestamps=include_timestamps, cursor=cursor)

    header_lines = [
        f"Title: {result['title'] or 'N/A'}",
        f"Duration: {result['duration']}s",
        f"Language: {result['lang']}",
        f"Source: {result['source']}",
        f"Length: {result['total_length']} chars (position {result['position']})",
    ]
    if result["next_cursor"]:
        header_lines.append(f"next_cursor: {result['next_cursor']}")
    else:
        header_lines.append("next_cursor: null")

    header = "\n".join(header_lines)
    return f"{header}\n---\n{result['text']}"


@mcp.tool()
def extract_frames(
    url: str,
    interval_seconds: int = 30,
    method: str = "interval",
    max_frames: int = 20,
    max_resolution: int = 720,
    quality: int = 60,
    start_time: int | None = None,
    end_time: int | None = None,
) -> list:
    """Extract frames from a YouTube video at regular intervals or scene changes.

    Returns frames as base64 JPEG images with timestamp labels.

    Args:
        url: YouTube video URL or video ID
        interval_seconds: Seconds between captures in interval mode (default: 30)
        method: "interval" for fixed timing, "scene" for scene-change detection
        max_frames: Maximum number of frames to return (default: 20)
        max_resolution: Max height in pixels for video download (default: 720)
        quality: JPEG compression quality 1-100 (default: 60)
        start_time: Start of segment in seconds (optional)
        end_time: End of segment in seconds (optional)
    """
    frames = extract_frames_from_video(
        url,
        interval_seconds=interval_seconds,
        method=method,
        max_frames=max_frames,
        max_resolution=max_resolution,
        quality=quality,
        start_time=start_time,
        end_time=end_time,
    )

    content_blocks = []
    for frame in frames:
        ts_label = format_timestamp(frame["timestamp"])
        content_blocks.append(
            types.ImageContent(
                type="image",
                data=frame["image_base64"],
                mimeType="image/jpeg",
            )
        )
        content_blocks.append(
            types.TextContent(type="text", text=ts_label)
        )
    return content_blocks


@mcp.tool()
def analyze_video(
    url: str,
    lang: str = "en",
    frame_interval: int = 60,
    max_frames: int = 10,
    quality: int = 50,
    start_time: int | None = None,
    end_time: int | None = None,
) -> list:
    """Analyze a YouTube video by fetching both transcript and frames together.

    Returns transcript segments interleaved with frames in chronological order.
    Uses tighter defaults than extract_frames to manage total output size.

    Args:
        url: YouTube video URL or video ID
        lang: Preferred transcript language (default: en)
        frame_interval: Seconds between frame captures (default: 60)
        max_frames: Maximum frames to return (default: 10)
        quality: JPEG compression quality 1-100 (default: 50)
        start_time: Start of segment in seconds (optional)
        end_time: End of segment in seconds (optional)
    """
    # Fetch complete transcript (all pages)
    text_parts = []
    cursor = None
    while True:
        result = _fetch_transcript(url, lang=lang, include_timestamps=True, cursor=cursor)
        text_parts.append(result["text"])
        cursor = result["next_cursor"]
        if cursor is None:
            break
    full_text = "".join(text_parts)

    # Extract frames (512px max height for combined output)
    frames = extract_frames_from_video(
        url,
        interval_seconds=frame_interval,
        method="interval",
        max_frames=max_frames,
        max_resolution=512,
        quality=quality,
        start_time=start_time,
        end_time=end_time,
    )

    # Interleave transcript segments with frames chronologically
    content_blocks = []

    transcript_lines = full_text.split("\n")
    frame_idx = 0
    segment_lines = []

    for line in transcript_lines:
        # Check if we should insert a frame before this line
        if frame_idx < len(frames):
            line_ts = extract_timestamp_seconds(line)
            if line_ts is not None and line_ts >= frames[frame_idx]["timestamp"]:
                segment_lines.append(line)
                if segment_lines:
                    content_blocks.append(
                        types.TextContent(type="text", text="\n".join(segment_lines))
                    )
                    segment_lines = []
                # Insert all frames up to this timestamp
                while frame_idx < len(frames) and line_ts >= frames[frame_idx]["timestamp"]:
                    frame = frames[frame_idx]
                    ts_label = format_timestamp(frame["timestamp"])
                    content_blocks.append(
                        types.ImageContent(
                            type="image",
                            data=frame["image_base64"],
                            mimeType="image/jpeg",
                        )
                    )
                    content_blocks.append(
                        types.TextContent(type="text", text=ts_label)
                    )
                    frame_idx += 1
                continue

        segment_lines.append(line)

    # Flush remaining transcript
    if segment_lines:
        content_blocks.append(
            types.TextContent(type="text", text="\n".join(segment_lines))
        )

    # Append any remaining frames past the end of the transcript
    while frame_idx < len(frames):
        frame = frames[frame_idx]
        ts_label = format_timestamp(frame["timestamp"])
        content_blocks.append(
            types.ImageContent(
                type="image",
                data=frame["image_base64"],
                mimeType="image/jpeg",
            )
        )
        content_blocks.append(
            types.TextContent(type="text", text=ts_label)
        )
        frame_idx += 1

    return content_blocks


def main():
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
