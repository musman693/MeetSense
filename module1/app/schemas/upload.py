"""
Pydantic schemas for Module 1 — Upload, Status & Transcript endpoints.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"


# ─── Upload ──────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Returned immediately after a file is accepted and queued."""

    job_id: str = Field(..., description="Unique job identifier — use to poll status")
    status: JobStatus = Field(JobStatus.QUEUED)
    filename: str = Field(..., description="Original filename as uploaded")
    file_type: FileType
    s3_key: str = Field(..., description="Storage key of the uploaded file")
    message: str = "File uploaded successfully. Processing has been queued."

    model_config = {"json_schema_extra": {
        "example": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "queued",
            "filename": "team_standup.mp4",
            "file_type": "video",
            "s3_key": "uploads/550e8400-e29b-41d4-a716-446655440000/team_standup.mp4",
            "message": "File uploaded successfully. Processing has been queued.",
        }
    }}


# ─── Status ───────────────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    """Processing status for a given job."""

    job_id: str
    status: JobStatus
    progress_pct: Optional[int] = Field(None, ge=0, le=100,
                                        description="Rough % completion (0-100)")
    error: Optional[str] = Field(None, description="Error message if status=failed")

    model_config = {"json_schema_extra": {
        "example": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "processing",
            "progress_pct": 45,
            "error": None,
        }
    }}


# ─── Transcript ───────────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    """One timestamped, speaker-labelled segment of speech."""

    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    speaker: str = Field(..., description="Speaker label, e.g. SPEAKER_00")
    text: str = Field(..., description="Transcribed text for this segment")

    model_config = {"json_schema_extra": {
        "example": {
            "start": 0.0,
            "end": 4.5,
            "speaker": "SPEAKER_00",
            "text": "Good morning everyone, let's get started.",
        }
    }}


class TranscriptResponse(BaseModel):
    """Full transcript with all speaker-labelled segments."""

    job_id: str
    status: JobStatus
    duration_seconds: Optional[float] = Field(None, description="Total recording length")
    num_speakers: Optional[int] = Field(None, description="Number of distinct speakers detected")
    segments: list[TranscriptSegment] = Field(default_factory=list)

    model_config = {"json_schema_extra": {
        "example": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "completed",
            "duration_seconds": 1823.4,
            "num_speakers": 3,
            "segments": [
                {"start": 0.0, "end": 4.5, "speaker": "SPEAKER_00",
                 "text": "Good morning everyone, let's get started."},
                {"start": 5.1, "end": 9.2, "speaker": "SPEAKER_01",
                 "text": "Thanks. I'll share the agenda first."},
            ],
        }
    }}
