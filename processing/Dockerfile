FROM python:3.14-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables
ENV ENTRYPOINT_PATH="/app/docker-entrypoint.sh" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Create app user
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Set work directory
WORKDIR /app

# Change ownership of /app directory to user "app"
RUN chown -R app:app /app

# Pre-create .venv so the Docker volume inherits correct ownership on first mount.
# Without this, the volume is initialized as root:root and the "app" user cannot install packages.
RUN mkdir -p /app/.venv && chown app:app /app/.venv

# Copy dependency files
COPY --chown=app:app pyproject.toml uv.lock ./

# Dependencies will be installed at runtime to avoid permission issues

# Copy source code
COPY --chown=app:app . .

# Ensure entrypoint script is executable
RUN chmod +x $ENTRYPOINT_PATH

# Execute entrypoint script to handle setup tasks before running the main command
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Switch to app user before installing dependencies to avoid permission issues
USER app

# Expose port for Django development server
EXPOSE 8000

# ---- Django development stage
FROM base AS dev
# -----------------------------

CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---- Django production stage
FROM base AS prod
# ----------------------------

RUN uv sync --frozen --no-dev
CMD ["uv", "run", "daphne", "-b", "0.0.0.0", "-p", "8000", "databus.asgi:application"]

# -- Celery Worker
FROM base AS tasks
# ----------------

CMD ["uv", "run", "celery", "-A", "databus", "worker", "-Q", "tasks", "--loglevel=info"]

# ------------ Celery Worker
FROM base AS realtime-engine
# --------------------------

CMD ["uv", "run", "celery", "-A", "databus", "worker", "-Q", "realtime_engine", "--loglevel=info"]

# -------- Celery Beat
FROM base AS scheduler
# --------------------

CMD ["uv", "run", "celery", "-A", "databus", "beat", "--loglevel=info"]
