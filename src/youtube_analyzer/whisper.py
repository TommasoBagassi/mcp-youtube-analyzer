# src/youtube_analyzer/whisper.py
"""Audio download and transcription via faster-whisper.

Used as fallback when no captions are available.
"""

import logging
import os
import tempfile

import yt_dlp

from .utils import format_timestamp, get_yt_dlp_cookie_opts

logger = logging.getLogger(__name__)

_model_cache = None
_model_cache_name = None


def _get_whisper_model():
    """Get or create cached WhisperModel instance."""
    global _model_cache, _model_cache_name
    from faster_whisper import WhisperModel

    model_name = _get_whisper_model_name()
    if _model_cache is None or _model_cache_name != model_name:
        logger.info("Loading Whisper model: %s", model_name)
        _model_cache = WhisperModel(model_name, device="cpu", compute_type="int8")
        _model_cache_name = model_name
    return _model_cache


def _get_whisper_model_name() -> str:
    """Get Whisper model name from env, default 'small'."""
    return os.environ.get("WHISPER_MODEL", "small")


def _download_audio(video_id: str, output_dir: str) -> str:
    """Download audio-only stream via yt-dlp. Returns path to audio file.

    Downloads native format (no conversion) to avoid needing system ffmpeg.
    faster-whisper can read most audio formats directly.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": f"{output_dir}/audio.%(ext)s",
        **get_yt_dlp_cookie_opts(),
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=True
        )
        return ydl.prepare_filename(info)


def transcribe_video(
    video_id: str, include_timestamps: bool = True
) -> str:
    """Download audio and transcribe with faster-whisper.

    Returns formatted transcript text.
    """
    model = _get_whisper_model()

    with tempfile.TemporaryDirectory() as tmpdir:
        logger.info("Downloading audio for %s", video_id)
        audio_path = _download_audio(video_id, tmpdir)

        logger.info("Transcribing with faster-whisper...")
        segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)

        # Segments is a generator that reads the audio file lazily,
        # so it must be fully consumed before the temp directory is cleaned up.
        lines = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            if include_timestamps:
                ts = format_timestamp(segment.start)
                lines.append(f"{ts} {text}")
            else:
                lines.append(text)

    return "\n".join(lines)
