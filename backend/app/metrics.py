"""Prometheus metrics definitions for observability (L8)."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

RESOLVE_REQUESTS = Counter(
    "vdl_resolve_requests_total",
    "Total resolve requests by platform and status",
    ["platform", "status", "cached"],
)

RESOLVE_DURATION = Histogram(
    "vdl_resolve_duration_seconds",
    "Resolve request duration in seconds",
    ["platform"],
    buckets=(0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 45.0),
)

JOBS_TOTAL = Counter(
    "vdl_jobs_total",
    "Total download jobs by platform and final status",
    ["platform", "status"],
)

JOB_DURATION = Histogram(
    "vdl_job_duration_seconds",
    "Download job duration in seconds",
    ["platform"],
    buckets=(1.0, 3.0, 5.0, 10.0, 20.0, 45.0, 90.0, 180.0, 600.0),
)

EXTRACTION_FAILURES = Counter(
    "vdl_extraction_failures_total",
    "Extraction failures by error code, platform, and proxy label",
    ["error_code", "platform", "proxy"],
)

QUEUE_DEPTH = Gauge(
    "vdl_queue_depth",
    "Current number of pending jobs in the Redis queue",
)

ACTIVE_JOBS = Gauge(
    "vdl_active_jobs",
    "Current number of active running jobs",
    ["platform"],
)

BYTES_SERVED = Counter(
    "vdl_bytes_served_total",
    "Total media bytes streamed to clients",
    ["platform"],
)

CANARY_STATUS = Gauge(
    "vdl_canary_platform_up",
    "Canary check status per platform (1 = healthy, 0 = degraded)",
    ["platform"],
)

CANARY_LATENCY = Gauge(
    "vdl_canary_latency_seconds",
    "Canary resolve latency per platform in seconds",
    ["platform"],
)

COOKIE_STATUS = Gauge(
    "vdl_cookie_valid",
    "Cookie file status per platform (1 = valid/present, 0 = expired/invalid, -1 = not configured)",
    ["platform"],
)

DISK_FREE_BYTES = Gauge(
    "vdl_storage_free_bytes",
    "Available disk space on download storage volume",
)
