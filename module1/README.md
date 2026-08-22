# MeetSense — Module 1: Audio/Video Processing, Speech-to-Text & Speaker Identification

**Handler:** Shayan | Backend Developer  
**Stack:** Python 3.11 · FastAPI · OpenAI Whisper · pyannote.audio · Celery · Redis · S3 (boto3)

---

## What This Module Does

Module 1 is the **entry point** of the MeetSense pipeline:

1. Accepts meeting audio or video file uploads via REST API  
2. Stores files securely in S3-compatible storage (AWS S3 / MinIO)  
3. Enqueues background Celery jobs so large files never block the API  
4. Runs **OpenAI Whisper** for accurate, timestamped speech-to-text  
5. Runs **pyannote.audio** (or a no-token fallback) for speaker diarization  
6. Merges transcript + speaker labels and delivers a structured JSON result  

---

## Project Structure

```
module1/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings (env vars)
│   ├── routers/
│   │   └── upload.py        # Upload, status, transcript endpoints
│   ├── services/
│   │   ├── storage.py       # S3 helpers
│   │   ├── transcription.py # Whisper STT
│   │   └── diarization.py   # Speaker diarization + merging
│   ├── workers/
│   │   └── tasks.py         # Celery pipeline task
│   └── schemas/
│       └── upload.py        # Pydantic request/response models
├── tests/
│   ├── test_upload.py       # Endpoint tests
│   ├── test_transcription.py
│   └── test_diarization.py
├── conftest.py
├── requirements.txt
├── .env.example
├── Dockerfile
└── README.md  ← you are here
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/upload/audio` | Upload an audio file (mp3, wav, m4a, ogg, flac, webm) |
| `POST` | `/api/v1/upload/video` | Upload a video file (mp4, mkv, avi, mov, webm) |
| `GET`  | `/api/v1/upload/{job_id}/status` | Poll processing status |
| `GET`  | `/api/v1/upload/{job_id}/transcript` | Fetch completed transcript |
| `GET`  | `/health` | Liveness probe |

Full interactive docs: **`http://localhost:8001/docs`**

---

## Supported File Formats

| Type | Formats |
|------|---------|
| Audio | `mp3` `wav` `m4a` `ogg` `flac` `webm` |
| Video | `mp4` `mkv` `avi` `mov` `webm` |

---

## Local Setup

### Prerequisites
- Python 3.11+
- [ffmpeg](https://ffmpeg.org/download.html) installed and on `PATH`
- Docker (for MinIO + Redis)

### 1. Clone & install

```bash
cd module1
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set HUGGINGFACE_TOKEN if using pyannote
```

### 3. Start Redis + MinIO (Docker)

```bash
# Redis
docker run -d -p 6379:6379 redis:7-alpine

# MinIO (S3-compatible local storage)
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

MinIO console → http://localhost:9001 (login: minioadmin / minioadmin)

### 4. Start the API server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 5. Start the Celery worker (separate terminal)

```bash
celery -A app.workers.tasks.celery_app worker --loglevel=info --concurrency=2
```

---

## Running Tests

```bash
cd module1
pytest tests/ -v --cov=app --cov-report=term-missing
```

Tests mock all external services (S3, Celery, Whisper, pyannote) — no internet or running services required.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `base` | Whisper model size: `tiny` / `base` / `small` / `medium` / `large` / `large-v3` |
| `WHISPER_LANGUAGE` | *(auto)* | ISO 639-1 code, e.g. `en`. Leave blank for auto-detect |
| `HUGGINGFACE_TOKEN` | *(none)* | Required for pyannote diarization. Leave blank for simple-diarizer fallback |
| `S3_ENDPOINT_URL` | *(AWS)* | Custom endpoint for MinIO. Remove for real AWS |
| `S3_BUCKET_NAME` | `meetsense` | S3 bucket name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `MAX_UPLOAD_SIZE_MB` | `500` | Max file upload size in MB |

---

## Integration with Other Modules

- **Module 3 (Noor)** — owns the PostgreSQL schema. Once her DB models are ready, replace the `transcript_s3_key`-only approach in `tasks.py` with a direct DB write via SQLAlchemy.  
- **Module 2 (Sultan)** — reads the transcript produced by this module to run summarization, action item extraction, etc.
- **Module 4 (Nouman)** — calls this module's endpoints from the frontend upload screen.

---

## Deliverable (per project spec)

> Working, tested Upload + Speech-to-Text + Speaker Identification backend service with API documentation, pushed to the shared repo every week.

✅ FastAPI endpoints (audio, video, status, transcript)  
✅ Whisper STT with timestamps  
✅ Speaker diarization (pyannote + fallback)  
✅ S3-compatible storage  
✅ Celery background processing  
✅ Unit tests for all components  
✅ OpenAPI docs at `/docs`  
