FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# System libs needed at runtime for Geo/GIS and Postgres
RUN apt-get update && \
    apt-get install -y \
    curl \
    gcc \
    g++ \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    libpq-dev \
    libspatialindex-dev \
    python3-dev \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# --------------------------
# Dependencies (prod)
# --------------------------
FROM base AS deps
COPY pyproject.toml ./
COPY uv.lock ./
RUN uv venv && uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"

# --------------------------
# Dependencies (dev)
# --------------------------
FROM base AS deps-dev
COPY pyproject.toml ./
COPY uv.lock ./
RUN uv venv && uv sync --frozen --group dev
ENV PATH="/app/.venv/bin:$PATH"

# --------------------------
# Development image
# --------------------------
FROM base AS dev
COPY --from=deps-dev /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . .
RUN chmod +x /app/entrypoint.dev.sh
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.dev.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --------------------------
# Production image (ASGI via Daphne)
# --------------------------
FROM base AS prod
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . .
RUN chmod +x /app/entrypoint.prod.sh
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.prod.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "realtime.asgi:application"]
