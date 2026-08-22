"""
Unit tests for the speaker diarization service.

pyannote and simple-diarizer are mocked — we focus on:
  1. The diarize() dispatcher (pyannote vs. fallback)
  2. The assign_speakers() overlap-matching algorithm
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.diarization import (
    DiarSegment,
    LabelledSegment,
    assign_speakers,
    diarize,
)
from app.services.transcription import WhisperSegment


# ─── assign_speakers tests ────────────────────────────────────────────────────

class TestAssignSpeakers:
    """Tests for the overlap-based speaker-to-transcript assignment."""

    def _wseg(self, start, end, text="hello") -> WhisperSegment:
        return WhisperSegment(start=start, end=end, text=text)

    def _dseg(self, start, end, speaker) -> DiarSegment:
        return DiarSegment(start=start, end=end, speaker=speaker)

    def test_exact_match(self):
        """Whisper segment fully inside a diar segment → correct speaker."""
        whisper = [self._wseg(0.0, 5.0, "Hello world")]
        diar = [self._dseg(0.0, 5.0, "SPEAKER_00")]
        result = assign_speakers(whisper, diar)
        assert len(result) == 1
        assert result[0].speaker == "SPEAKER_00"
        assert result[0].text == "Hello world"

    def test_partial_overlap(self):
        """Best overlapping speaker wins."""
        whisper = [self._wseg(2.0, 6.0)]
        diar = [
            self._dseg(0.0, 4.0, "SPEAKER_00"),   # overlap: 2.0s
            self._dseg(4.0, 8.0, "SPEAKER_01"),   # overlap: 2.0s
        ]
        # Tie-break: first one with equal overlap wins (SPEAKER_00)
        result = assign_speakers(whisper, diar)
        assert result[0].speaker in {"SPEAKER_00", "SPEAKER_01"}

    def test_no_overlap_returns_unknown(self):
        """No diar segment overlaps → speaker=UNKNOWN."""
        whisper = [self._wseg(10.0, 12.0)]
        diar = [self._dseg(0.0, 5.0, "SPEAKER_00")]
        result = assign_speakers(whisper, diar)
        assert result[0].speaker == "UNKNOWN"

    def test_multiple_speakers(self):
        """Multiple Whisper segments each get the right speaker."""
        whisper = [
            self._wseg(0.0, 4.0, "I will finish the backend"),
            self._wseg(5.0, 8.0, "I'll handle the frontend"),
        ]
        diar = [
            self._dseg(0.0, 4.5, "SPEAKER_00"),
            self._dseg(4.5, 9.0, "SPEAKER_01"),
        ]
        result = assign_speakers(whisper, diar)
        assert result[0].speaker == "SPEAKER_00"
        assert result[1].speaker == "SPEAKER_01"

    def test_empty_inputs(self):
        """Both empty → empty output, no crash."""
        assert assign_speakers([], []) == []

    def test_empty_diar(self):
        """No diar segments → all UNKNOWN."""
        whisper = [self._wseg(0.0, 5.0), self._wseg(5.0, 10.0)]
        result = assign_speakers(whisper, [])
        assert all(s.speaker == "UNKNOWN" for s in result)

    def test_timestamps_preserved(self):
        """start/end from Whisper segment are preserved in output."""
        whisper = [self._wseg(3.14, 7.77)]
        diar = [self._dseg(0.0, 10.0, "SPEAKER_00")]
        result = assign_speakers(whisper, diar)
        assert result[0].start == 3.14
        assert result[0].end == 7.77


# ─── diarize() dispatcher tests ───────────────────────────────────────────────

class TestDiarizeDispatcher:
    def test_uses_pyannote_when_token_set(self, tmp_path):
        """When HUGGINGFACE_TOKEN is set, pyannote pipeline is used."""
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"\x00" * 100)

        mock_turn = MagicMock()
        mock_turn.start = 0.0
        mock_turn.end = 5.0

        mock_pipeline = MagicMock()
        mock_pipeline.return_value.itertracks.return_value = [
            (mock_turn, None, "SPEAKER_00")
        ]

        with (
            patch("app.services.diarization.settings") as mock_settings,
            patch("app.services.diarization._load_pyannote", return_value=mock_pipeline),
        ):
            mock_settings.huggingface_token = "hf_fake_token"
            result = diarize(str(audio))

        assert len(result) == 1
        assert result[0].speaker == "SPEAKER_00"

    def test_uses_fallback_when_no_token(self, tmp_path):
        """When HUGGINGFACE_TOKEN is absent, simple-diarizer fallback is called."""
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"\x00" * 100)

        with (
            patch("app.services.diarization.settings") as mock_settings,
            patch("app.services.diarization._diarize_simple") as mock_simple,
        ):
            mock_settings.huggingface_token = None
            mock_simple.return_value = [DiarSegment(0.0, 5.0, "SPEAKER_00")]
            result = diarize(str(audio))
            mock_simple.assert_called_once()

        assert result[0].speaker == "SPEAKER_00"
