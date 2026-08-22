"""
Module 1 — Application settings.
All values are read from environment variables (or a .env file).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_secret_key: str = "change-me"

    # ── S3 ───────────────────────────────────────────────────────────────────
    s3_endpoint_url: str | None = None          # None → real AWS
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket_name: str = "meetsense"
    s3_region: str = "us-east-1"

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── Whisper ───────────────────────────────────────────────────────────────
    whisper_model: str = "base"
    whisper_language: str | None = None         # None → auto-detect

    # ── pyannote ─────────────────────────────────────────────────────────────
    huggingface_token: str | None = None

    # ── Database (Module 3) ───────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://meetsense:meetsense@localhost:5432/meetsense"

    # ── Upload limits ─────────────────────────────────────────────────────────
    max_upload_size_mb: int = 500

    @field_validator("whisper_model")
    @classmethod
    def validate_whisper_model(cls, v: str) -> str:
        allowed = {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"}
        if v not in allowed:
            raise ValueError(f"whisper_model must be one of {allowed}")
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


# Singleton — import this everywhere
settings = Settings()
