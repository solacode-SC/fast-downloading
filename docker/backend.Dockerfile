ARG PYTHON_VERSION=3.12.8

FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/var/lib/vdl/ytdlp-overlay:/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
        tini \
        ca-certificates \
        curl \
        libcurl4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml

# ------------------------------------------------------------------
# Development target (includes pytest, ruff, mypy, pip-audit, hot reload)
# ------------------------------------------------------------------
FROM base AS dev

RUN mkdir -p /app/app && touch /app/app/__init__.py \
    && pip install --no-cache-dir -e ".[dev]"

COPY backend/ /app/

RUN mkdir -p /var/lib/vdl/downloads /var/lib/vdl/ytdlp-overlay /tmp/vdl

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--loop", "uvloop"]

# ------------------------------------------------------------------
# Production target (non-root user, minimal surface, tini init)
# ------------------------------------------------------------------
FROM base AS prod

RUN mkdir -p /app/app && touch /app/app/__init__.py \
    && pip install --no-cache-dir "." \
    && rm -rf /app/app

COPY backend/app /app/app

RUN groupadd --gid 10001 vdl \
    && useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin --create-home vdl \
    && mkdir -p /var/lib/vdl/downloads /var/lib/vdl/ytdlp-overlay /tmp/vdl /run/secrets/cookies \
    && chown -R vdl:vdl /app /var/lib/vdl /tmp/vdl

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD ["curl", "-fsS", "http://127.0.0.1:8000/healthz"]

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "uvloop", "--http", "httptools", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "30"]
