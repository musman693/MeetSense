"""
Unit tests for the Whisper transcription service.

Whisper is mocked — we test the service's data transformation logic
without running actual STT inference.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Patch whisper.load_model BEFORE importing the service to avoid loading the model
with patch("whisper.load_model", return_value=MagicMock()):
    from app.services.transcription import transcribe, transcribe_bytes, WhisperSegment


# ─── Fixtures ────────────────────────────────────────────────────────────────

MOCK_WHISPER_RESULT = {
    "segments": [
        {"start": 0.0,  "end": 4.5,  "text": "  Good morning everyone.  "},
        {"start": 5.1,  "end": 9.2,  "text": "Let's get started."},
        {"start": 10.0, "end": 15.3, "text": "  I'll share the agenda.  "},
    ]
}


def _make_temp_audio() -> str:
    """Create a tiny temp file that looks like an audio file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(b"\x00" * 100)
    tmp.close()
    return tmp.name


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestTranscribe:
    def test_returns_whisper_segments(self):
        """transcribe() converts raw Whisper output to WhisperSegment dataclasses."""
        audio_path = _make_temp_audio()
        try:
            with patch("app.services.transcription._model") as mock_model:
                mock_model.transcribe.return_value = MOCK_WHISPER_RESULT
                segments = transcribe(audio_path)
        finally:
            os.unlink(audio_path)

        assert len(segments) == 3
        assert all(isinstance(s, WhisperSegment) for s in segments)

    def test_text_is_stripped(self):
        """Leading/trailing whitespace is stripped from each segment's text."""
        audio_path = _make_temp_audio()
        try:
            with patch("app.services.transcription._model") as mock_model:
                mock_model.transcribe.return_value = MOCK_WHISPER_RESULT
                segments = transcribe(audio_path)
        finally:
            os.unlink(audio_path)

        assert segments[0].text == "Good morning everyone."
        assert segments[2].text == "I'll share the agenda."

    def test_timestamps_are_preserved(self):
        """start/end timestamps from Whisper are preserved."""
        audio_path = _make_temp_audio()
        try:
            with patch("app.services.transcription._model") as mock_model:
                mock_model.transcribe.return_value = MOCK_WHISPER_RESULT
                segments = transcribe(audio_path)
        finally:
            os.unlink(audio_path)

        assert segments[0].start == 0.0
        assert segments[0].end == 4.5
        assert segments[1].start == 5.1

    def test_file_not_found_raises(self):
        """Passing a non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            transcribe("/nonexistent/path/audio.wav")

    def test_empty_segments(self):
        """Whisper returning zero segments → empty list (no crash)."""
        audio_path = _make_temp_audio()
        try:
            with patch("app.services.transcription._model") as mock_model:
                mock_model.transcribe.return_value = {"segments": []}
                segments = transcribe(audio_path)
        finally:
            os.unlink(audio_path)

        assert segments == []

    def test_transcribe_bytes(self):
        """transcribe_bytes() writes bytes to a temp file and returns segments."""
        with patch("app.services.transcription._model") as mock_model:
            mock_model.transcribe.return_value = MOCK_WHISPER_RESULT
            segments = transcribe_bytes(b"\x00" * 100, suffix=".wav")

        assert len(segments) == 3
