# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for ffmpeg, pyannote, torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# ffmpeg must also be present at runtime
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ ./app/

# Non-root user for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8001

# Default: run the FastAPI API server
# Override CMD to "celery -A app.workers.tasks.celery_app worker ..." for workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
