# =============================================================================
# # ARECCA — Automated Real Estate Contract Compliance Auditor
# Multi-stage Dockerfile
# =============================================================================

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libffi-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel hatchling

# Pre-build wheels for all dependencies (caches layers for faster rebuilds)
COPY pyproject.toml .
COPY src/ src/
RUN pip wheel --no-cache-dir --wheel-dir=/app/wheels . && \
    pip wheel --no-cache-dir --wheel-dir=/app/wheels ".[dev]"

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG DEBIAN_FRONTEND=noninteractive
ARG APP_USER=arecca
ARG APP_GROUP=arecca
ARG APP_HOME=/app
ARG APP_PORT=8000

# System dependencies for runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and group
RUN groupadd --system --gid 1001 ${APP_GROUP} && \
    useradd --system --uid 1001 --gid ${APP_GROUP} --home ${APP_HOME} --shell /sbin/nologin ${APP_USER}

WORKDIR ${APP_HOME}

# Copy pre-built wheels from builder
COPY --from=builder /app/wheels /app/wheels

# Install wheels (no internet needed, pure local install)
RUN pip install --no-cache-dir --no-index --find-links=/app/wheels arecca && \
    rm -rf /app/wheels

# Create required directories with correct permissions (including Hugging Face & Fastembed caches)
RUN mkdir -p ${APP_HOME}/data/memory \
             ${APP_HOME}/data/uploads \
             ${APP_HOME}/data/cache/huggingface \
             ${APP_HOME}/data/cache/fastembed \
             ${APP_HOME}/configs \
             ${APP_HOME}/prompts \
             ${APP_HOME}/prompts/extraction \
             ${APP_HOME}/prompts/compliance \
    && chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME}/data

# Persist uploaded PDFs and memory outside the container
VOLUME ${APP_HOME}/data/uploads
VOLUME ${APP_HOME}/data/memory

# Copy runtime configs, prompts, and scripts
COPY --chown=${APP_USER}:${APP_GROUP} configs/ ${APP_HOME}/configs/
COPY --chown=${APP_USER}:${APP_GROUP} prompts/ ${APP_HOME}/prompts/
COPY --chown=${APP_USER}:${APP_GROUP} scripts/ ${APP_HOME}/scripts/

# Copy .env.example as reference (real .env mounted at runtime)
COPY --chown=${APP_USER}:${APP_GROUP} .env.example ${APP_HOME}/.env.example

# Set Environment Variables to redirect ML Model caches to our writable directory
ENV HF_HOME=${APP_HOME}/data/cache/huggingface
ENV FASTEMBED_CACHE_DIR=${APP_HOME}/data/cache/fastembed

# Expose application port
EXPOSE ${APP_PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:${APP_PORT}/health || exit 1

# Drop privileges
USER ${APP_USER}

# Default command - Executes using the installed Python package path
CMD ["uvicorn", "arecca.api.main:app", "--host", "0.0.0.0", "--port", "8000"]