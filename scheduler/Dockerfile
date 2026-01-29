# Minimal Python runtime for Celery-based services
FROM python:3.14-slim AS base

# Install only essential system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Create non-root user
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

WORKDIR /app

# Change ownership of /app directory to app user
RUN chown -R app:app /app

# Copy dependency manifests first (better caching)
COPY --chown=app:app pyproject.toml uv.lock ./

# Switch to app user before uv sync
USER app

# Sync uv as app user to avoid permission issues
RUN uv sync

# Copy source code
COPY --chown=app:app . .
