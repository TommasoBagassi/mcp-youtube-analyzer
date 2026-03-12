# tests/test_server.py
"""Tests for server tool functions."""

from unittest.mock import patch, MagicMock

import mcp.types as types

from youtube_analyzer.server import analyze_video
from youtube_analyzer.server import mcp as mcp_server


class TestServerInstructions:
    def test_server_has_instructions(self):
        assert mcp_server.instructions is not None
        assert len(mcp_server.instructions) > 0

    def test_instructions_mention_youtube_tools(self):
        instructions = mcp_server.instructions
        assert "get_transcript" in instructions
        assert "extract_frames" in instructions
        assert "analyze_video" in instructions
        assert "get_video_info" in instructions


class TestAnalyzeVideoInterleaving:
    @patch("youtube_analyzer.server.extract_frames_from_video")
    @patch("youtube_analyzer.server._fetch_transcript")
    def test_interleaves_frames_with_transcript(self, mock_transcript, mock_frames):
        mock_transcript.return_value = {
            "text": "[0:00] Hello\n[0:30] World\n[1:00] End",
            "source": "captions",
            "next_cursor": None,
            "total_length": 100,
            "position": 0,
            "title": "Test",
            "duration": 60,
            "lang": "en",
        }
        mock_frames.return_value = [
            {"timestamp": 30, "image_base64": "abc123"},
        ]

        result = analyze_video("dQw4w9WgXcQ")

        # Should have: text segment, image, text label, remaining text
        text_blocks = [b for b in result if isinstance(b, types.TextContent)]
        image_blocks = [b for b in result if isinstance(b, types.ImageContent)]
        assert len(image_blocks) == 1
        assert len(text_blocks) >= 2  # At least transcript + timestamp label

    @patch("youtube_analyzer.server.extract_frames_from_video")
    @patch("youtube_analyzer.server._fetch_transcript")
    def test_handles_empty_frames(self, mock_transcript, mock_frames):
        mock_transcript.return_value = {
            "text": "[0:00] Hello world",
            "source": "captions",
            "next_cursor": None,
            "total_length": 50,
            "position": 0,
            "title": "Test",
            "duration": 60,
            "lang": "en",
        }
        mock_frames.return_value = []

        result = analyze_video("dQw4w9WgXcQ")
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "Hello world" in result[0].text

    @patch("youtube_analyzer.server.extract_frames_from_video")
    @patch("youtube_analyzer.server._fetch_transcript")
    def test_appends_frames_past_transcript(self, mock_transcript, mock_frames):
        mock_transcript.return_value = {
            "text": "[0:00] Short",
            "source": "captions",
            "next_cursor": None,
            "total_length": 30,
            "position": 0,
            "title": "Test",
            "duration": 120,
            "lang": "en",
        }
        mock_frames.return_value = [
            {"timestamp": 60, "image_base64": "frame1"},
            {"timestamp": 90, "image_base64": "frame2"},
        ]

        result = analyze_video("dQw4w9WgXcQ")
        image_blocks = [b for b in result if isinstance(b, types.ImageContent)]
        assert len(image_blocks) == 2  # Both frames appended after transcript

    @patch("youtube_analyzer.server.extract_frames_from_video")
    @patch("youtube_analyzer.server._fetch_transcript")
    def test_multiple_frames_same_timestamp_range(self, mock_transcript, mock_frames):
        mock_transcript.return_value = {
            "text": "[0:00] Start\n[1:00] Middle\n[2:00] End",
            "source": "captions",
            "next_cursor": None,
            "total_length": 100,
            "position": 0,
            "title": "Test",
            "duration": 120,
            "lang": "en",
        }
        mock_frames.return_value = [
            {"timestamp": 0, "image_base64": "frame0"},
            {"timestamp": 30, "image_base64": "frame30"},
            {"timestamp": 90, "image_base64": "frame90"},
        ]

        result = analyze_video("dQw4w9WgXcQ")
        image_blocks = [b for b in result if isinstance(b, types.ImageContent)]
        assert len(image_blocks) == 3  # All 3 frames present
