# tests/test_integration.py
"""Integration tests against real YouTube videos.

Run with: uv run pytest tests/test_integration.py --integration -v
"""

import pytest

from youtube_analyzer.video_info import fetch_video_info
from youtube_analyzer.transcript import fetch_transcript
from youtube_analyzer.frames import extract_frames_from_video

# Short, stable, public video for testing
# "Me at the zoo" — first YouTube video, 19 seconds
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


@pytest.mark.integration
class TestVideoInfoIntegration:
    def test_fetches_real_metadata(self):
        info = fetch_video_info(TEST_VIDEO_URL)
        assert info["title"] is not None
        assert info["duration"] > 0
        assert info["channel"] is not None


@pytest.mark.integration
class TestTranscriptIntegration:
    def test_fetches_real_transcript(self):
        result = fetch_transcript(TEST_VIDEO_URL, lang="en")
        assert len(result["text"]) > 0
        assert result["source"] in ("captions", "yt-dlp-subtitles", "whisper")


@pytest.mark.integration
class TestExtractFramesIntegration:
    def test_extracts_real_frames(self):
        frames = extract_frames_from_video(
            TEST_VIDEO_URL,
            interval_seconds=10,
            max_frames=3,
            max_resolution=360,
            quality=30,
        )
        assert len(frames) > 0
        assert "image_base64" in frames[0]
        assert "timestamp" in frames[0]
