# src/youtube_analyzer/frames.py
"""Video download and frame extraction.

Pipeline: yt-dlp (video-only download) -> pyav (decode/seek) -> Pillow (resize) -> base64
"""

import logging
import tempfile

import av
import yt_dlp
from PIL import Image as PILImage

from .utils import (
    encode_image_base64,
    get_max_duration,
    get_yt_dlp_cookie_opts,
    parse_video_id,
    suppress_stdout,
)


def sample_frames(frames: list, max_frames: int) -> list:
    """Evenly sample frames, keeping first and last."""
    if len(frames) <= max_frames:
        return frames
    if max_frames == 1:
        return [frames[0]]
    if max_frames == 2:
        return [frames[0], frames[-1]]

    indices = [0]
    step = (len(frames) - 1) / (max_frames - 1)
    for i in range(1, max_frames - 1):
        indices.append(round(i * step))
    indices.append(len(frames) - 1)

    return [frames[i] for i in indices]


def resize_frame(image: PILImage.Image, max_height: int) -> PILImage.Image:
    """Resize image to fit within max_height, preserving aspect ratio."""
    if image.height <= max_height:
        return image
    ratio = max_height / image.height
    new_width = round(image.width * ratio)
    return image.resize((new_width, max_height), PILImage.Resampling.LANCZOS)


def download_video(video_id: str, output_dir: str, max_resolution: int = 720) -> str:
    """Download video-only stream via yt-dlp. Returns path to downloaded file.

    Checks duration before downloading to avoid wasting bandwidth.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    base_opts = {
        "quiet": True,
        "no_warnings": True,
        **get_yt_dlp_cookie_opts(),
    }

    # Check duration before downloading
    with yt_dlp.YoutubeDL({**base_opts, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        if info is None:
            raise RuntimeError("yt-dlp returned no metadata for this video")
        duration = info.get("duration", 0)
        max_dur = get_max_duration()
        if duration > max_dur:
            raise ValueError(
                f"Video is {duration / 3600:.1f} hours. "
                f"Max is {max_dur / 3600:.1f} hours. "
                f"Set YOUTUBE_MAX_DURATION to override"
            )

    # Download video-only stream
    dl_opts = {
        **base_opts,
        "format": f"bestvideo[height<={max_resolution}]/bestvideo/best",
        "outtmpl": f"{output_dir}/video.%(ext)s",
    }

    with suppress_stdout(), yt_dlp.YoutubeDL(dl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def extract_frames_interval(
    video_path: str,
    interval_seconds: int = 30,
    max_frames: int = 20,
    max_height: int = 720,
    quality: int = 60,
    start_time: int | None = None,
    end_time: int | None = None,
) -> list[dict]:
    """Extract frames at regular intervals using pyav.

    Returns list of dicts with keys: timestamp, image_base64
    """
    with av.open(video_path) as container:
        stream = container.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration else 0

        # Validate time range
        start = start_time if start_time is not None else 0
        end = end_time if end_time is not None else int(duration)
        if end_time is not None and end_time > duration:
            end = int(duration)
        if start >= end:
            raise ValueError(f"Invalid time range: start_time={start} >= end_time={end}")

        # Calculate target timestamps
        timestamps = list(range(start, end, interval_seconds))
        if not timestamps:
            timestamps = [start]

        # Extract frames at each timestamp
        raw_frames = []
        for ts in timestamps:
            target_pts = int(ts / stream.time_base)
            container.seek(target_pts, stream=stream)
            for frame in container.decode(video=0):
                raw_frames.append({"timestamp": ts, "frame": frame})
                break  # Only need the first frame after seek

    # Sample if too many
    raw_frames = sample_frames(raw_frames, max_frames)

    # Convert to output format
    results = []
    for item in raw_frames:
        pil_image = item["frame"].to_image()
        pil_image = resize_frame(pil_image, max_height)
        b64 = encode_image_base64(pil_image, quality)
        results.append({
            "timestamp": item["timestamp"],
            "image_base64": b64,
        })

    return results


def extract_frames_from_video(
    url: str,
    interval_seconds: int = 30,
    method: str = "interval",
    max_frames: int = 20,
    max_resolution: int = 720,
    quality: int = 60,
    start_time: int | None = None,
    end_time: int | None = None,
) -> list[dict]:
    """Full pipeline: download video, extract frames, clean up.

    Returns list of dicts with keys: timestamp, image_base64
    """
    video_id = parse_video_id(url)

    # Validate time range early
    if start_time is not None and end_time is not None and start_time >= end_time:
        raise ValueError(
            f"Invalid time range: start_time={start_time} >= end_time={end_time}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            video_path = download_video(video_id, tmpdir, max_resolution)
        except Exception as e:
            raise RuntimeError(f"Frame extraction failed during download: {e}") from e

        try:
            if method == "scene":
                return _extract_frames_scene(
                    video_path,
                    max_frames=max_frames,
                    max_height=max_resolution,
                    quality=quality,
                    start_time=start_time,
                    end_time=end_time,
                )
            else:
                return extract_frames_interval(
                    video_path,
                    interval_seconds=interval_seconds,
                    max_frames=max_frames,
                    max_height=max_resolution,
                    quality=quality,
                    start_time=start_time,
                    end_time=end_time,
                )
        except ValueError:
            raise  # Re-raise validation errors as-is
        except Exception as e:
            raise RuntimeError(f"Frame extraction failed during decode: {e}") from e


def _extract_frames_scene(
    video_path: str,
    max_frames: int,
    max_height: int,
    quality: int,
    start_time: int | None,
    end_time: int | None,
) -> list[dict]:
    """Extract frames at scene changes using scenedetect."""
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector

    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()
    del video  # Release scenedetect's file handle before opening with pyav

    if not scene_list:
        # No scenes detected; fall back to interval extraction
        return extract_frames_interval(
            video_path, interval_seconds=30, max_frames=max_frames,
            max_height=max_height, quality=quality,
            start_time=start_time, end_time=end_time
        )

    # Get the start timestamp of each scene
    timestamps = []
    for scene_start, _scene_end in scene_list:
        ts = scene_start.get_seconds()
        if start_time is not None and ts < start_time:
            continue
        if end_time is not None and ts > end_time:
            break
        timestamps.append(int(ts))

    if not timestamps:
        timestamps = [start_time if start_time is not None else 0]

    # Extract frames at scene boundaries using pyav
    with av.open(video_path) as container:
        stream = container.streams.video[0]

        raw_frames = []
        for ts in timestamps:
            target_pts = int(ts / stream.time_base)
            container.seek(target_pts, stream=stream)
            for frame in container.decode(video=0):
                raw_frames.append({"timestamp": ts, "frame": frame})
                break

    raw_frames = sample_frames(raw_frames, max_frames)

    results = []
    for item in raw_frames:
        pil_image = item["frame"].to_image()
        pil_image = resize_frame(pil_image, max_height)
        b64 = encode_image_base64(pil_image, quality)
        results.append({
            "timestamp": item["timestamp"],
            "image_base64": b64,
        })

    return results
