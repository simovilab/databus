# Multi-stage build for Django app
FROM python:3.14-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    libffi-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app user
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Set work directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy source code (needed for both stages)
COPY . .

# ---- Development stage
FROM base as dev
# -------------------

# Set work directory
WORKDIR /app

# Ensure entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh && \
    chmod +x /app/scripts/*.sh

USER app

# Expose port for Django development server
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---- Production stage
FROM base as prod
# ------------------

# Set work directory
WORKDIR /app

# Ensure entrypoint script executable and create directories
RUN chmod +x /app/docker-entrypoint.sh && \
    chmod +x /app/scripts/*.sh && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R app:app /app/staticfiles /app/media

USER app

# Expose port for gunicorn
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "realtime.wsgi:application"]
