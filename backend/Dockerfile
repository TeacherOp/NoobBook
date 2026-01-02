# Backend Dockerfile - Multi-stage build
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    libreoffice \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

WORKDIR /app

# Development base with playwright
FROM base AS dev-base
RUN pip install playwright && playwright install --with-deps chromium

# Development stage
FROM dev-base AS development
COPY backend/requirements.txt .
RUN uv pip install --system -r requirements.txt
COPY backend/ .
EXPOSE 5000
CMD ["python", "run.py"]

# Production stage
FROM base AS production
COPY backend/requirements.txt .
RUN uv pip install --system -r requirements.txt && \
    uv pip install --system gunicorn
COPY backend/ .

# Create non-root user
RUN useradd --create-home --shell /bin/bash noobbook && \
    chown -R noobbook:noobbook /app
USER noobbook

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/api/v1/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "300", "run:app"]
