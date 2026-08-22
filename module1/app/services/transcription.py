"""
Speech-to-Text service using OpenAI Whisper.

Supports:
  - Common audio formats: mp3, wav, m4a, ogg, flac, webm
  - Common video formats (audio extracted first by the worker)
  - Preserved start/end timestamps per segment
  - Long recordings (Whisper handles chunking internally via its 30-s window approach)

The model is loaded once at module import time and reused across calls
(avoid reloading on every request — it's expensive).
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Optional

import whisper

from app.config import settings

logger = logging.getLogger(__name__)

# ── Load model once ──────────────────────────────────────────────────────────
logger.info("Loading Whisper model: %s", settings.whisper_model)
_model = whisper.load_model(settings.whisper_model)
logger.info("Whisper model loaded.")


@dataclass
class WhisperSegment:
    """One timestamped speech segment from Whisper."""
    start: float   # seconds
    end: float     # seconds
    text: str


def transcribe(audio_path: str, language: Optional[str] = None) -> list[WhisperSegment]:
    """
    Transcribe the audio file at *audio_path* using Whisper.

    Parameters
    ----------
    audio_path : str
        Absolute path to an audio file (mp3/wav/m4a/ogg/flac/webm …).
        Video files should be pre-converted to audio by the caller.
    language : str | None
        ISO 639-1 language code (e.g. "en", "ur"). Pass None for auto-detect.

    Returns
    -------
    list[WhisperSegment]
        Time-ordered list of segments, each with start/end/text.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    kwargs: dict = {
        "verbose": False,
        "word_timestamps": False,   # set True if token-level timestamps are needed later
    }
    if language:
        kwargs["language"] = language
    elif settings.whisper_language:
        kwargs["language"] = settings.whisper_language

    logger.info("Starting transcription: %s (model=%s)", audio_path, settings.whisper_model)
    result = _model.transcribe(audio_path, **kwargs)

    segments: list[WhisperSegment] = []
    for seg in result.get("segments", []):
        segments.append(WhisperSegment(
            start=round(seg["start"], 3),
            end=round(seg["end"], 3),
            text=seg["text"].strip(),
        ))

    logger.info("Transcription complete: %d segments", len(segments))
    return segments


def transcribe_bytes(audio_bytes: bytes, suffix: str = ".wav",
                     language: Optional[str] = None) -> list[WhisperSegment]:
    """
    Convenience wrapper: write *audio_bytes* to a temp file then transcribe.

    Useful when the caller already has the file in memory (e.g. after S3 download).
    """
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        return transcribe(tmp_path, language=language)
    finally:
        os.unlink(tmp_path)
