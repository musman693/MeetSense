"""
Upload router — Module 1 public API.

Endpoints:
  POST /api/v1/upload/audio          → accept audio file, queue processing
  POST /api/v1/upload/video          → accept video file, queue processing
  GET  /api/v1/upload/{job_id}/status    → poll job status
  GET  /api/v1/upload/{job_id}/transcript → fetch completed transcript
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated

from celery.result import AsyncResult
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import settings
from app.schemas.upload import (
    FileType,
    JobStatus,
    StatusResponse,
    TranscriptResponse,
    TranscriptSegment,
    UploadResponse,
)
from app.services import storage
from app.workers.tasks import celery_app, process_meeting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/upload", tags=["Upload"])

# ── Allowed MIME types ────────────────────────────────────────────────────────

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",          # .mp3
    "audio/wav",           # .wav
    "audio/x-wav",
    "audio/mp4",           # .m4a
    "audio/x-m4a",
    "audio/ogg",           # .ogg
    "audio/flac",          # .flac
    "audio/webm",          # .webm audio
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",           # .mp4
    "video/x-matroska",   # .mkv
    "video/x-msvideo",    # .avi
    "video/quicktime",    # .mov
    "video/webm",         # .webm video
}


def _validate_upload(file: UploadFile, allowed_types: set[str]) -> None:
    """Raise 400/413 for bad MIME type or oversize files."""
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed: {sorted(allowed_types)}",
        )


async def _handle_upload(file: UploadFile, file_type: FileType) -> UploadResponse:
    """Shared upload logic for audio and video."""
    job_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
    s3_key = f"uploads/{job_id}/{file.filename}"

    # Read file content — FastAPI streams it; check size in memory
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB.",
        )

    # Upload to S3
    storage.upload_file(content, s3_key, content_type=file.content_type)
    logger.info("Queuing job %s for %s file: %s", job_id, file_type, file.filename)

    # Enqueue Celery task
    process_meeting.apply_async(
        kwargs={
            "job_id": job_id,
            "s3_key": s3_key,
            "file_type": file_type.value,
        },
        task_id=job_id,
    )

    return UploadResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        filename=file.filename,
        file_type=file_type,
        s3_key=s3_key,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/audio",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload an audio file for processing",
    description=(
        "Upload an audio recording (mp3, wav, m4a, ogg, flac, webm). "
        "The file is stored securely and queued for transcription + speaker identification. "
        "Returns a `job_id` to poll `/status` and eventually `/transcript`."
    ),
)
async def upload_audio(
    file: Annotated[UploadFile, File(description="Audio file to process")],
) -> UploadResponse:
    _validate_upload(file, ALLOWED_AUDIO_TYPES)
    return await _handle_upload(file, FileType.AUDIO)


@router.post(
    "/video",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a video file for processing",
    description=(
        "Upload a meeting video recording (mp4, mkv, avi, mov, webm). "
        "Audio is automatically extracted before transcription. "
        "Returns a `job_id` to poll `/status` and eventually `/transcript`."
    ),
)
async def upload_video(
    file: Annotated[UploadFile, File(description="Video file to process")],
) -> UploadResponse:
    _validate_upload(file, ALLOWED_VIDEO_TYPES)
    return await _handle_upload(file, FileType.VIDEO)


@router.get(
    "/{job_id}/status",
    response_model=StatusResponse,
    summary="Poll the processing status of a job",
)
async def get_status(job_id: str) -> StatusResponse:
    result = AsyncResult(job_id, app=celery_app)

    state = result.state          # PENDING | STARTED | PROGRESS | SUCCESS | FAILURE

    if state == "PENDING":
        return StatusResponse(job_id=job_id, status=JobStatus.QUEUED)

    if state == "PROGRESS":
        meta = result.info or {}
        return StatusResponse(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress_pct=meta.get("progress_pct"),
        )

    if state == "SUCCESS":
        info = result.result or {}
        if info.get("status") == "failed":
            return StatusResponse(
                job_id=job_id,
                status=JobStatus.FAILED,
                error=info.get("error"),
            )
        return StatusResponse(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            progress_pct=100,
        )

    if state == "FAILURE":
        return StatusResponse(
            job_id=job_id,
            status=JobStatus.FAILED,
            error=str(result.info),
        )

    # STARTED or other
    return StatusResponse(job_id=job_id, status=JobStatus.PROCESSING, progress_pct=0)


@router.get(
    "/{job_id}/transcript",
    response_model=TranscriptResponse,
    summary="Fetch the completed transcript for a job",
)
async def get_transcript(job_id: str) -> TranscriptResponse:
    result = AsyncResult(job_id, app=celery_app)

    if result.state != "SUCCESS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is not completed yet (state={result.state}). "
                   "Poll /status until status=completed.",
        )

    info = result.result or {}
    if info.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job failed: {info.get('error')}",
        )

    # Fetch full transcript JSON from S3 (task result only holds metadata)
    transcript_key = info.get("transcript_s3_key")
    if not transcript_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found for this job.",
        )

    raw = storage.download_file(transcript_key)
    segments_data: list[dict] = json.loads(raw.decode("utf-8"))

    segments = [
        TranscriptSegment(
            start=seg["start"],
            end=seg["end"],
            speaker=seg["speaker"],
            text=seg["text"],
        )
        for seg in segments_data
    ]

    return TranscriptResponse(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        duration_seconds=info.get("duration_seconds"),
        num_speakers=info.get("num_speakers"),
        segments=segments,
    )
