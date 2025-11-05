# Multi-stage build for Django app with uv
FROM python:3.14-slim as base

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
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Create app user
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Dependencies will be installed at runtime to avoid permission issues

# ---- Development stage
FROM base as dev
# -------------------

# Copy source code
COPY --chown=app:app . .

# Ensure entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

USER app

# Expose port for Django development server
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---- Production stage
FROM base as prod
# ------------------

# Copy source code
COPY --chown=app:app . .

# Ensure entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Create static files and media directories
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R app:app /app/staticfiles /app/media

# Clean up any existing venv and set proper permissions
RUN rm -rf /app/.venv && \
    chown -R app:app /app

# Switch to app user before installing dependencies to avoid permission issues
USER app

# Install dependencies in production mode
RUN uv sync --frozen --no-dev

# Expose port for ASGI server
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uv", "run", "daphne", "-b", "0.0.0.0", "-p", "8000", "realtime.asgi:application"]
