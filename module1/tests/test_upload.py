"""
Unit tests for the Upload endpoints (POST /audio, POST /video, GET /status, GET /transcript).

S3 is mocked with moto. Celery tasks are mocked so the worker doesn't actually run.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.upload import JobStatus


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Return a synchronous TestClient for the FastAPI app."""
    return TestClient(app)


def _make_mp3(size_kb: int = 1) -> bytes:
    """Minimal MP3-like bytes (just zeros, enough for upload size checks)."""
    return b"\x00" * (size_kb * 1024)


# ─── POST /api/v1/upload/audio ────────────────────────────────────────────────

class TestAudioUpload:
    def test_upload_audio_success(self, client):
        """A valid MP3 upload returns 202 with a job_id."""
        with (
            patch("app.routers.upload.storage.upload_file", return_value="uploads/x/f.mp3"),
            patch("app.routers.upload.process_meeting.apply_async") as mock_task,
        ):
            mock_task.return_value = MagicMock(id="fake-job-id")
            resp = client.post(
                "/api/v1/upload/audio",
                files={"file": ("meeting.mp3", _make_mp3(), "audio/mpeg")},
            )

        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "queued"
        assert body["file_type"] == "audio"
        assert body["filename"] == "meeting.mp3"

    def test_upload_audio_wrong_mime(self, client):
        """Uploading an exe as audio should return 415."""
        resp = client.post(
            "/api/v1/upload/audio",
            files={"file": ("virus.exe", b"\x00", "application/octet-stream")},
        )
        assert resp.status_code == 415

    def test_upload_audio_too_large(self, client):
        """Files exceeding MAX_UPLOAD_SIZE_MB should return 413."""
        # Temporarily set a tiny limit
        with patch("app.routers.upload.settings") as mock_settings:
            mock_settings.max_upload_size_bytes = 10   # 10 bytes limit
            mock_settings.max_upload_size_mb = 0
            with (
                patch("app.routers.upload.storage.upload_file"),
                patch("app.routers.upload.process_meeting.apply_async"),
            ):
                resp = client.post(
                    "/api/v1/upload/audio",
                    files={"file": ("big.mp3", _make_mp3(size_kb=1), "audio/mpeg")},
                )
        assert resp.status_code == 413


# ─── POST /api/v1/upload/video ────────────────────────────────────────────────

class TestVideoUpload:
    def test_upload_video_success(self, client):
        """A valid MP4 upload returns 202 with file_type=video."""
        with (
            patch("app.routers.upload.storage.upload_file", return_value="uploads/x/f.mp4"),
            patch("app.routers.upload.process_meeting.apply_async") as mock_task,
        ):
            mock_task.return_value = MagicMock(id="fake-job-id")
            resp = client.post(
                "/api/v1/upload/video",
                files={"file": ("standup.mp4", _make_mp3(), "video/mp4")},
            )

        assert resp.status_code == 202
        body = resp.json()
        assert body["file_type"] == "video"

    def test_upload_video_wrong_mime(self, client):
        """Uploading an audio file to /video should return 415."""
        resp = client.post(
            "/api/v1/upload/video",
            files={"file": ("audio.mp3", b"\x00", "audio/mpeg")},
        )
        assert resp.status_code == 415


# ─── GET /api/v1/upload/{job_id}/status ──────────────────────────────────────

class TestStatus:
    def test_status_queued(self, client):
        """PENDING Celery state → status=queued."""
        with patch("app.routers.upload.AsyncResult") as mock_ar:
            mock_ar.return_value.state = "PENDING"
            resp = client.get("/api/v1/upload/some-job-id/status")

        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

    def test_status_processing(self, client):
        """PROGRESS state → status=processing with progress_pct."""
        with patch("app.routers.upload.AsyncResult") as mock_ar:
            ar = MagicMock()
            ar.state = "PROGRESS"
            ar.info = {"progress_pct": 45, "step": "Transcribing"}
            mock_ar.return_value = ar
            resp = client.get("/api/v1/upload/some-job-id/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "processing"
        assert body["progress_pct"] == 45

    def test_status_completed(self, client):
        """SUCCESS state → status=completed."""
        with patch("app.routers.upload.AsyncResult") as mock_ar:
            ar = MagicMock()
            ar.state = "SUCCESS"
            ar.result = {"status": "completed", "duration_seconds": 123.4}
            mock_ar.return_value = ar
            resp = client.get("/api/v1/upload/some-job-id/status")

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["progress_pct"] == 100

    def test_status_failed(self, client):
        """FAILURE state → status=failed with error."""
        with patch("app.routers.upload.AsyncResult") as mock_ar:
            ar = MagicMock()
            ar.state = "FAILURE"
            ar.info = Exception("Whisper crashed")
            mock_ar.return_value = ar
            resp = client.get("/api/v1/upload/some-job-id/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "error" in body


# ─── GET /api/v1/upload/{job_id}/transcript ──────────────────────────────────

class TestTranscript:
    _SEGMENTS = [
        {"start": 0.0, "end": 4.5, "speaker": "SPEAKER_00",
         "text": "Good morning everyone."},
        {"start": 5.1, "end": 9.2, "speaker": "SPEAKER_01",
         "text": "Let's get started."},
    ]

    def test_get_transcript_success(self, client):
        """Completed job → returns segments with speakers + timestamps."""
        with (
            patch("app.routers.upload.AsyncResult") as mock_ar,
            patch("app.routers.upload.storage.download_file",
                  return_value=json.dumps(self._SEGMENTS).encode()),
        ):
            ar = MagicMock()
            ar.state = "SUCCESS"
            ar.result = {
                "status": "completed",
                "duration_seconds": 9.2,
                "num_speakers": 2,
                "transcript_s3_key": "transcripts/abc/transcript.json",
            }
            mock_ar.return_value = ar
            resp = client.get("/api/v1/upload/abc/transcript")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["num_speakers"] == 2
        assert len(body["segments"]) == 2
        assert body["segments"][0]["speaker"] == "SPEAKER_00"

    def test_get_transcript_not_ready(self, client):
        """Polling transcript before job completes → 409 Conflict."""
        with patch("app.routers.upload.AsyncResult") as mock_ar:
            ar = MagicMock()
            ar.state = "PROGRESS"
            mock_ar.return_value = ar
            resp = client.get("/api/v1/upload/abc/transcript")

        assert resp.status_code == 409


# ─── Health check ─────────────────────────────────────────────────────────────

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
