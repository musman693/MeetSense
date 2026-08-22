"""
Speaker Diarization service.

Primary: pyannote.audio 3.x (state-of-the-art, requires HuggingFace token).
Fallback: simple-diarizer (no token needed, lower accuracy) — activated
          automatically when HUGGINGFACE_TOKEN is not set.

The diarization result is merged with Whisper segments using a
timestamp-overlap strategy so each segment gets a speaker label.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass

from app.config import settings
from app.services.transcription import WhisperSegment

logger = logging.getLogger(__name__)


# ─── Data structures ─────────────────────────────────────────────────────────

@dataclass
class DiarSegment:
    """One speaker turn from the diarizer."""
    start: float
    end: float
    speaker: str   # e.g. "SPEAKER_00"


@dataclass
class LabelledSegment:
    """Whisper segment enriched with a speaker label."""
    start: float
    end: float
    speaker: str
    text: str


# ─── pyannote pipeline (lazy-loaded) ────────────────────────────────────────

_pyannote_pipeline = None


def _load_pyannote():
    global _pyannote_pipeline
    if _pyannote_pipeline is not None:
        return _pyannote_pipeline

    from pyannote.audio import Pipeline
    token = settings.huggingface_token
    if not token:
        raise RuntimeError(
            "HUGGINGFACE_TOKEN is not set. "
            "Either set it or leave it blank to use the simple-diarizer fallback."
        )
    logger.info("Loading pyannote speaker-diarization-3.1 pipeline…")
    _pyannote_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=token,
    )
    logger.info("pyannote pipeline loaded.")
    return _pyannote_pipeline


# ─── simple-diarizer fallback ────────────────────────────────────────────────

def _diarize_simple(audio_path: str) -> list[DiarSegment]:
    """
    Fallback diarizer using simple-diarizer (pip install simple-diarizer).
    No HuggingFace token required.
    """
    try:
        from simple_diarizer.diarizer import Diarizer  # type: ignore
    except ImportError:
        raise ImportError(
            "simple-diarizer is not installed. "
            "Run: pip install simple-diarizer"
        )

    diar = Diarizer(embed_model="ecapa", cluster_method="ahc")
    segments_raw = diar.diarize(audio_path, num_speakers=None)

    result: list[DiarSegment] = []
    for seg in segments_raw:
        result.append(DiarSegment(
            start=round(seg["start"], 3),
            end=round(seg["end"], 3),
            speaker=f"SPEAKER_{int(seg['label']):02d}",
        ))
    return result


# ─── pyannote diarizer ───────────────────────────────────────────────────────

def _diarize_pyannote(audio_path: str) -> list[DiarSegment]:
    pipeline = _load_pyannote()
    diarization = pipeline(audio_path)

    result: list[DiarSegment] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        result.append(DiarSegment(
            start=round(turn.start, 3),
            end=round(turn.end, 3),
            speaker=speaker,
        ))
    return result


# ─── Public API ──────────────────────────────────────────────────────────────

def diarize(audio_path: str) -> list[DiarSegment]:
    """
    Run speaker diarization on *audio_path*.

    Automatically selects pyannote (if token available) or simple-diarizer.
    """
    if settings.huggingface_token:
        logger.info("Using pyannote diarizer.")
        return _diarize_pyannote(audio_path)
    else:
        logger.info("No HuggingFace token — using simple-diarizer fallback.")
        return _diarize_simple(audio_path)


def diarize_bytes(audio_bytes: bytes, suffix: str = ".wav") -> list[DiarSegment]:
    """Convenience wrapper: write bytes to temp file, then diarize."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        return diarize(tmp_path)
    finally:
        os.unlink(tmp_path)


# ─── Merge transcript + diarization ─────────────────────────────────────────

def assign_speakers(
    whisper_segments: list[WhisperSegment],
    diar_segments: list[DiarSegment],
) -> list[LabelledSegment]:
    """
    Assign a speaker label to each Whisper segment using maximum-overlap matching.

    For every Whisper segment we find the diarization segment that overlaps
    it the most. If no overlap is found, the segment is labelled "UNKNOWN".
    """
    labelled: list[LabelledSegment] = []

    for wseg in whisper_segments:
        best_speaker = "UNKNOWN"
        best_overlap = 0.0

        for dseg in diar_segments:
            # Compute overlap between [wseg.start, wseg.end] and [dseg.start, dseg.end]
            overlap_start = max(wseg.start, dseg.start)
            overlap_end = min(wseg.end, dseg.end)
            overlap = max(0.0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = dseg.speaker

        labelled.append(LabelledSegment(
            start=wseg.start,
            end=wseg.end,
            speaker=best_speaker,
            text=wseg.text,
        ))

    return labelled
