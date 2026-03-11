# tests/test_frames.py
"""Tests for frame extraction."""

import base64
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage

from youtube_analyzer.frames import sample_frames, resize_frame


class TestSampleFrames:
    def test_no_sampling_needed(self):
        frames = list(range(5))
        result = sample_frames(frames, max_frames=10)
        assert result == [0, 1, 2, 3, 4]

    def test_samples_evenly(self):
        frames = list(range(100))
        result = sample_frames(frames, max_frames=5)
        assert len(result) == 5
        assert result[0] == 0       # first
        assert result[-1] == 99     # last

    def test_max_frames_one(self):
        frames = list(range(10))
        result = sample_frames(frames, max_frames=1)
        assert len(result) == 1
        assert result[0] == 0

    def test_max_frames_two(self):
        frames = list(range(10))
        result = sample_frames(frames, max_frames=2)
        assert len(result) == 2
        assert result[0] == 0
        assert result[-1] == 9

    def test_empty_list(self):
        assert sample_frames([], max_frames=5) == []

    def test_240_to_20_keeps_first_and_last(self):
        """Spec example: 240 frames → max 20 = correct distribution."""
        frames = list(range(240))
        result = sample_frames(frames, max_frames=20)
        assert len(result) == 20
        assert result[0] == 0        # first
        assert result[-1] == 239     # last
        # Verify even spacing
        for i in range(1, len(result)):
            assert result[i] > result[i - 1]


class TestTimeRangeValidation:
    def test_start_equals_end_raises(self):
        from youtube_analyzer.frames import extract_frames_from_video
        with pytest.raises(ValueError, match="Invalid time range"):
            extract_frames_from_video("dQw4w9WgXcQ", start_time=10, end_time=10)

    def test_start_greater_than_end_raises(self):
        from youtube_analyzer.frames import extract_frames_from_video
        with pytest.raises(ValueError, match="Invalid time range"):
            extract_frames_from_video("dQw4w9WgXcQ", start_time=20, end_time=10)


class TestResizeFrame:
    def test_resize_tall_image(self):
        img = PILImage.new("RGB", (1920, 1080))
        result = resize_frame(img, max_height=720)
        assert result.height == 720
        assert result.width == 1280

    def test_no_resize_needed(self):
        img = PILImage.new("RGB", (640, 480))
        result = resize_frame(img, max_height=720)
        assert result.size == (640, 480)

    def test_preserves_aspect_ratio(self):
        img = PILImage.new("RGB", (800, 600))
        result = resize_frame(img, max_height=300)
        assert result.height == 300
        assert result.width == 400
