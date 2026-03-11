# tests/test_video_info.py
"""Tests for video info extraction."""

from unittest.mock import patch

import pytest

from youtube_analyzer.video_info import fetch_video_info


class TestFetchVideoInfo:
    @patch("youtube_analyzer.video_info.yt_dlp.YoutubeDL")
    def test_returns_metadata(self, mock_ydl_class):
        mock_ydl = mock_ydl_class.return_value.__enter__.return_value
        mock_ydl.extract_info.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "duration": 120,
            "upload_date": "20240101",
            "description": "A test video",
            "view_count": 1000,
            "subtitles": {"en": []},
            "automatic_captions": {"en": [], "fr": []},
        }

        result = fetch_video_info("dQw4w9WgXcQ")
        assert result["title"] == "Test Video"
        assert result["channel"] == "Test Channel"
        assert result["duration"] == 120
        assert "en" in result["subtitle_languages"]

    @patch("youtube_analyzer.video_info.yt_dlp.YoutubeDL")
    def test_rejects_long_video(self, mock_ydl_class, monkeypatch):
        monkeypatch.setenv("YOUTUBE_MAX_DURATION", "60")
        mock_ydl = mock_ydl_class.return_value.__enter__.return_value
        mock_ydl.extract_info.return_value = {
            "title": "Long Video",
            "duration": 7200,
            "subtitles": {},
            "automatic_captions": {},
        }

        with pytest.raises(ValueError, match="Max is"):
            fetch_video_info("dQw4w9WgXcQ")

    @patch("youtube_analyzer.video_info.yt_dlp.YoutubeDL")
    def test_private_video_without_cookies(self, mock_ydl_class, monkeypatch):
        monkeypatch.delenv("YOUTUBE_COOKIE_SOURCE", raising=False)
        monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
        from yt_dlp.utils import DownloadError
        mock_ydl = mock_ydl_class.return_value.__enter__.return_value
        mock_ydl.extract_info.side_effect = DownloadError("This video is private")
        with pytest.raises(ValueError, match="Video is private"):
            fetch_video_info("dQw4w9WgXcQ")
