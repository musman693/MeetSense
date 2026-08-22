"""
Module 1 — FastAPI application entry point.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers.upload import router as upload_router
from app.services.storage import ensure_bucket_exists

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if settings.app_env != "development" else logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="MeetSense — Module 1: Audio/Video Processing",
    description=(
        "Upload meeting recordings (audio or video), "
        "get back speaker-labelled, timestamped transcripts. "
        "Powered by OpenAI Whisper + pyannote speaker diarization."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (wide-open for dev; tighten in production) ───────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(upload_router)


# ── Startup / shutdown events ─────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Starting MeetSense Module 1 (env=%s)", settings.app_env)
    try:
        ensure_bucket_exists()
    except Exception as exc:
        logger.warning("Could not ensure S3 bucket exists: %s", exc)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Liveness probe")
async def health_check():
    return JSONResponse({"status": "ok", "module": "module1"})


@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "message": "MeetSense Module 1 — Audio/Video Processing API",
        "docs": "/docs",
    })
