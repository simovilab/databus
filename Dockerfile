FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && \
    apt-get install -y \
    build-essential \
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

# Install uv using pip instead of copying from ghcr.io
RUN pip install uv

# Install project dependencies from pyproject (use lockfile if present)
COPY pyproject.toml ./
COPY uv.lock ./
RUN uv sync --frozen

# Copy the application source
COPY . . 

# Activate virtual environment by updating PATH
ENV PATH="/app/.venv/bin:$PATH"

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
