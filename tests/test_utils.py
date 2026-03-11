# tests/test_utils.py
"""Tests for utility functions."""

import base64

import pytest
from PIL import Image as PILImage

from youtube_analyzer.utils import parse_video_id
from youtube_analyzer.utils import (
    extract_timestamp_seconds,
    format_timestamp,
    get_max_duration,
    get_yt_dlp_cookie_opts,
    encode_image_base64,
)


class TestParseVideoId:
    def test_standard_watch_url(self):
        assert parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert parse_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert parse_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert parse_video_id("https://youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_bare_video_id(self):
        assert parse_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_extra_params(self):
        assert parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120") == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Could not parse YouTube video ID"):
            parse_video_id("https://example.com/not-youtube")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_video_id("")


class TestFormatTimestamp:
    def test_zero(self):
        assert format_timestamp(0.0) == "[0:00]"

    def test_seconds_only(self):
        assert format_timestamp(45.0) == "[0:45]"

    def test_minutes_and_seconds(self):
        assert format_timestamp(125.0) == "[2:05]"

    def test_hours(self):
        assert format_timestamp(3661.0) == "[1:01:01]"

    def test_fractional_seconds_truncated(self):
        assert format_timestamp(62.7) == "[1:02]"


class TestGetYtDlpCookieOpts:
    def test_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_COOKIE_SOURCE", raising=False)
        monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
        assert get_yt_dlp_cookie_opts() == {}

    def test_cookie_source(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_COOKIE_SOURCE", "firefox")
        monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookie_opts()
        assert result == {"cookiesfrombrowser": ("firefox",)}

    def test_cookies_file(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_COOKIE_SOURCE", raising=False)
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", "/path/to/cookies.txt")
        monkeypatch.setattr("youtube_analyzer.utils.os.path.isfile", lambda p: True)
        result = get_yt_dlp_cookie_opts()
        assert result == {"cookiefile": "/path/to/cookies.txt"}

    def test_cookie_source_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_COOKIE_SOURCE", "firefox")
        monkeypatch.setenv("YOUTUBE_COOKIES_FILE", "/path/to/cookies.txt")
        result = get_yt_dlp_cookie_opts()
        assert result == {"cookiesfrombrowser": ("firefox",)}


class TestGetMaxDuration:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_MAX_DURATION", raising=False)
        assert get_max_duration() == 10800

    def test_custom(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_MAX_DURATION", "7200")
        assert get_max_duration() == 7200


class TestEncodeImageBase64:
    def test_returns_base64_string(self):
        img = PILImage.new("RGB", (100, 100), color="red")
        result = encode_image_base64(img, quality=50)
        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert len(decoded) > 0


class TestExtractTimestampSeconds:
    def test_minutes_seconds(self):
        assert extract_timestamp_seconds("[1:30] some text") == 90

    def test_hours_minutes_seconds(self):
        assert extract_timestamp_seconds("[1:02:30] long video") == 3750

    def test_zero(self):
        assert extract_timestamp_seconds("[0:00] start") == 0

    def test_no_timestamp(self):
        assert extract_timestamp_seconds("no timestamp here") is None

    def test_timestamp_not_at_start(self):
        assert extract_timestamp_seconds("text [1:30] middle") is None
