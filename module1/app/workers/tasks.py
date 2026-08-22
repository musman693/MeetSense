"""
Celery background tasks for Module 1.

Flow for each job:
  1. Download raw file from S3
  2. If video → extract audio with ffmpeg
  3. Run Whisper transcription
  4. Run speaker diarization
  5. Merge transcript + speaker labels
  6. Persist result to the database (stub — wired to Module 3 schema)
  7. Update job status in Redis
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import uuid

from celery import Celery
from celery.utils.log import get_task_logger

from app.config import settings
from app.services import storage, transcription, diarization

# ── Celery app ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "module1",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # re-queue on worker crash
    worker_prefetch_multiplier=1,  # one job at a time per worker
)

logger = get_task_logger(__name__)

# ── Status helpers (stored in Celery result backend / Redis) ──────────────────

STATUS_KEY = "job:{job_id}:status"

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}


def _set_status(job_id: str, status: str, progress: int = 0, error: str = "") -> None:
    """Persist job status dict as the Celery task result."""
    # We use the task result backend for this — callers read via AsyncResult.
    # The router endpoint caches status separately in Redis for fast polling.
    pass   # actual update happens via self.update_state() inside the task


def _extract_audio(video_path: str, output_path: str) -> None:
    """Use ffmpeg to strip audio from a video file."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",                      # no video
        "-acodec", "pcm_s16le",     # WAV output — Whisper loves it
        "-ar", "16000",             # 16 kHz sample rate
        "-ac", "1",                 # mono
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")


# ── Main Celery task ──────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="module1.process_meeting", max_retries=2)
def process_meeting(self, job_id: str, s3_key: str, file_type: str) -> dict:
    """
    Full meeting processing pipeline.

    Parameters
    ----------
    job_id   : Unique job identifier (UUID string)
    s3_key   : S3 key of the uploaded file
    file_type: "audio" or "video"
    """
    tmpdir = tempfile.mkdtemp(prefix=f"meetsense_{job_id}_")
    raw_path = audio_path = None

    try:
        # ── Step 1: Download from S3 ────────────────────────────────────────
        self.update_state(state="PROGRESS",
                          meta={"progress_pct": 5, "step": "Downloading file"})
        logger.info("[%s] Downloading s3_key=%s", job_id, s3_key)

        file_bytes = storage.download_file(s3_key)
        ext = os.path.splitext(s3_key)[-1].lower() or ".bin"
        raw_path = os.path.join(tmpdir, f"raw{ext}")
        with open(raw_path, "wb") as f:
            f.write(file_bytes)

        # ── Step 2: Extract audio if video ──────────────────────────────────
        if file_type == "video" or ext in VIDEO_EXTENSIONS:
            self.update_state(state="PROGRESS",
                              meta={"progress_pct": 15, "step": "Extracting audio"})
            logger.info("[%s] Extracting audio from video", job_id)
            audio_path = os.path.join(tmpdir, "audio.wav")
            _extract_audio(raw_path, audio_path)
        else:
            audio_path = raw_path

        # ── Step 3: Transcription ────────────────────────────────────────────
        self.update_state(state="PROGRESS",
                          meta={"progress_pct": 30, "step": "Transcribing"})
        logger.info("[%s] Running Whisper transcription", job_id)
        whisper_segments = transcription.transcribe(audio_path)

        # ── Step 4: Diarization ──────────────────────────────────────────────
        self.update_state(state="PROGRESS",
                          meta={"progress_pct": 65, "step": "Speaker identification"})
        logger.info("[%s] Running speaker diarization", job_id)
        diar_segments = diarization.diarize(audio_path)

        # ── Step 5: Merge ────────────────────────────────────────────────────
        self.update_state(state="PROGRESS",
                          meta={"progress_pct": 85, "step": "Merging transcript"})
        logger.info("[%s] Assigning speakers to segments", job_id)
        labelled = diarization.assign_speakers(whisper_segments, diar_segments)

        # ── Step 6: Persist transcript to S3 (JSON) ──────────────────────────
        self.update_state(state="PROGRESS",
                          meta={"progress_pct": 92, "step": "Saving transcript"})

        segments_payload = [
            {
                "start": seg.start,
                "end": seg.end,
                "speaker": seg.speaker,
                "text": seg.text,
            }
            for seg in labelled
        ]

        transcript_key = f"transcripts/{job_id}/transcript.json"
        storage.upload_file(
            file_bytes=json.dumps(segments_payload, ensure_ascii=False).encode("utf-8"),
            s3_key=transcript_key,
            content_type="application/json",
        )

        # ── Step 7: Compute metadata ─────────────────────────────────────────
        duration = labelled[-1].end if labelled else 0.0
        speakers = sorted({seg.speaker for seg in labelled})

        result = {
            "job_id": job_id,
            "status": "completed",
            "duration_seconds": round(duration, 2),
            "num_speakers": len(speakers),
            "transcript_s3_key": transcript_key,
            "segments": segments_payload,
        }

        logger.info("[%s] Processing complete. Duration=%.1fs, Speakers=%d",
                    job_id, duration, len(speakers))
        return result

    except Exception as exc:
        logger.error("[%s] Processing failed: %s", job_id, exc, exc_info=True)
        try:
            self.retry(exc=exc, countdown=30)
        except self.MaxRetriesExceededError:
            return {
                "job_id": job_id,
                "status": "failed",
                "error": str(exc),
            }
    finally:
        # Clean up temp files
        import shutil
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)
