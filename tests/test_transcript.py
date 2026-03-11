# tests/test_transcript.py
"""Tests for transcript extraction."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from youtube_analyzer.transcript import _parse_vtt, fetch_transcript


class TestFetchTranscript:
    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_fetches_captions_with_timestamps(self, mock_api_class, mock_info):
        mock_info.return_value = {"title": "Test Video", "duration": 120}
        mock_snippet_1 = MagicMock(text="Hello world", start=0.0, duration=2.0)
        mock_snippet_2 = MagicMock(text="How are you", start=2.0, duration=3.0)
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = MagicMock(return_value=iter([mock_snippet_1, mock_snippet_2]))
        mock_api_class.return_value.fetch.return_value = mock_fetched

        result = fetch_transcript("dQw4w9WgXcQ", lang="en", include_timestamps=True)
        assert "[0:00]" in result["text"]
        assert "Hello world" in result["text"]
        assert result["source"] == "captions"

    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_fetches_captions_without_timestamps(self, mock_api_class, mock_info):
        mock_info.return_value = {"title": "Test Video", "duration": 120}
        mock_snippet = MagicMock(text="Hello world", start=0.0, duration=2.0)
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = MagicMock(return_value=iter([mock_snippet]))
        mock_api_class.return_value.fetch.return_value = mock_fetched

        result = fetch_transcript("dQw4w9WgXcQ", include_timestamps=False)
        assert "[0:00]" not in result["text"]
        assert "Hello world" in result["text"]

    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_result_includes_metadata(self, mock_api_class, mock_info):
        mock_info.return_value = {"title": "Test Video", "duration": 120}
        mock_snippet = MagicMock(text="Hello", start=0.0, duration=2.0)
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = MagicMock(return_value=iter([mock_snippet]))
        mock_api_class.return_value.fetch.return_value = mock_fetched

        result = fetch_transcript("dQw4w9WgXcQ", lang="en")
        assert result["title"] == "Test Video"
        assert result["duration"] == 120
        assert result["lang"] == "en"

    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_no_captions_no_whisper_raises(self, mock_api_class, mock_info):
        mock_info.return_value = {"title": "Test", "duration": 60}
        mock_api_class.return_value.fetch.side_effect = Exception("No captions")

        with patch("youtube_analyzer.transcript.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = mock_ydl_class.return_value.__enter__.return_value
            mock_ydl.download.side_effect = Exception("No subtitles")

            with pytest.raises(RuntimeError, match="No captions available"):
                fetch_transcript("dQw4w9WgXcQ")


class TestTranscriptPagination:
    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_pagination_splits_long_transcript(self, mock_api_class, mock_info):
        mock_info.return_value = {"title": "Test Video", "duration": 120}
        long_text = "Word " * 12000
        mock_snippet = MagicMock(text=long_text, start=0.0, duration=100.0)
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = MagicMock(return_value=iter([mock_snippet]))
        mock_api_class.return_value.fetch.return_value = mock_fetched

        result = fetch_transcript("dQw4w9WgXcQ", include_timestamps=False)
        assert result["next_cursor"] is not None
        assert len(result["text"]) <= 50000
        assert result["total_length"] > 50000

    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_pagination_cursor_fetches_next_chunk(self, mock_api_class, mock_info):
        mock_info.return_value = {"title": "Test Video", "duration": 120}
        long_text = "Word " * 12000
        mock_snippet = MagicMock(text=long_text, start=0.0, duration=100.0)
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = MagicMock(return_value=iter([mock_snippet]))
        mock_api_class.return_value.fetch.return_value = mock_fetched

        first = fetch_transcript("dQw4w9WgXcQ", include_timestamps=False)
        second = fetch_transcript(
            "dQw4w9WgXcQ", include_timestamps=False, cursor=first["next_cursor"]
        )
        assert second["position"] > 0

    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_no_pagination_for_short_transcript(self, mock_api_class, mock_info):
        mock_info.return_value = {"title": "Test Video", "duration": 120}
        mock_snippet = MagicMock(text="Short video", start=0.0, duration=5.0)
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = MagicMock(return_value=iter([mock_snippet]))
        mock_api_class.return_value.fetch.return_value = mock_fetched

        result = fetch_transcript("dQw4w9WgXcQ")
        assert result["next_cursor"] is None

    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_pagination_splits_on_sentence_boundary(self, mock_api_class, mock_info):
        mock_info.return_value = {"title": "Test Video", "duration": 120}
        sentences = "This is a sentence. " * 2800
        mock_snippet = MagicMock(text=sentences, start=0.0, duration=100.0)
        mock_fetched = MagicMock()
        mock_fetched.__iter__ = MagicMock(return_value=iter([mock_snippet]))
        mock_api_class.return_value.fetch.return_value = mock_fetched

        result = fetch_transcript("dQw4w9WgXcQ", include_timestamps=False)
        assert result["text"].endswith(". ")
        assert result["next_cursor"] is not None


class TestParseVtt:
    def test_basic_vtt(self, tmp_path):
        vtt = tmp_path / "test.vtt"
        vtt.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "Hello world\n\n"
            "00:00:05.500 --> 00:00:08.000\n"
            "Second line\n\n"
        )
        result = _parse_vtt(str(vtt), include_timestamps=True)
        assert "[0:01]" in result
        assert "Hello world" in result
        assert "[0:05]" in result
        assert "Second line" in result

    def test_vtt_without_timestamps(self, tmp_path):
        vtt = tmp_path / "test.vtt"
        vtt.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "Hello world\n\n"
        )
        result = _parse_vtt(str(vtt), include_timestamps=False)
        assert "[" not in result
        assert "Hello world" in result

    def test_vtt_deduplicates_repeated_lines(self, tmp_path):
        vtt = tmp_path / "test.vtt"
        vtt.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "Hello world\n\n"
            "00:00:03.000 --> 00:00:05.000\n"
            "Hello world\n\n"
            "00:00:05.000 --> 00:00:07.000\n"
            "Different text\n\n"
        )
        result = _parse_vtt(str(vtt), include_timestamps=False)
        assert result.count("Hello world") == 1
        assert "Different text" in result

    def test_vtt_strips_html_tags(self, tmp_path):
        vtt = tmp_path / "test.vtt"
        vtt.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "<c.colorE5E5E5>Hello</c> <c.colorCCCCCC>world</c>\n\n"
        )
        result = _parse_vtt(str(vtt), include_timestamps=False)
        assert "<" not in result
        assert "Hello world" in result

    def test_vtt_handles_mm_ss_format(self, tmp_path):
        vtt = tmp_path / "test.vtt"
        vtt.write_text(
            "WEBVTT\n\n"
            "01:30.000 --> 01:35.000\n"
            "Short format\n\n"
        )
        result = _parse_vtt(str(vtt), include_timestamps=True)
        assert "[1:30]" in result
        assert "Short format" in result

    def test_vtt_handles_hours_format(self, tmp_path):
        vtt = tmp_path / "test.vtt"
        vtt.write_text(
            "WEBVTT\n\n"
            "01:02:30.000 --> 01:02:35.000\n"
            "Long video\n\n"
        )
        result = _parse_vtt(str(vtt), include_timestamps=True)
        assert "[1:02:30]" in result
        assert "Long video" in result


class TestWhisperFallback:
    @patch("youtube_analyzer.transcript.fetch_video_info")
    @patch("youtube_analyzer.transcript._fetch_via_ytdlp")
    @patch("youtube_analyzer.transcript.YouTubeTranscriptApi")
    def test_falls_back_to_whisper(self, mock_api_class, mock_ytdlp, mock_info):
        mock_info.return_value = {"title": "Test", "duration": 60}
        mock_api_class.return_value.fetch.side_effect = Exception("No captions")
        mock_ytdlp.side_effect = Exception("No subtitles")

        with patch.dict(sys.modules, {"faster_whisper": MagicMock()}):
            with patch("youtube_analyzer.whisper.transcribe_video", return_value="[0:00] Whispered text"):
                result = fetch_transcript("dQw4w9WgXcQ")
                assert result["source"] == "whisper"
                assert "Whispered text" in result["text"]


class TestWhisperConfig:
    def test_whisper_model_default(self, monkeypatch):
        monkeypatch.delenv("WHISPER_MODEL", raising=False)
        from youtube_analyzer.whisper import _get_whisper_model_name
        assert _get_whisper_model_name() == "small"

    def test_whisper_model_custom(self, monkeypatch):
        monkeypatch.setenv("WHISPER_MODEL", "large-v3")
        from youtube_analyzer.whisper import _get_whisper_model_name
        assert _get_whisper_model_name() == "large-v3"
