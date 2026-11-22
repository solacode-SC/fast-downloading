# Operations Runbook

## 1. Updating `yt-dlp` (Zero-Rebuild Runtime Update)

`yt-dlp` updates automatically daily at `03:15 UTC` (when `YTDLP_AUTO_UPDATE=true`) into the writable `/var/lib/vdl/ytdlp-overlay` volume with an automated self-test and rollback.

To trigger an immediate manual update and verify the new version:
```bash
make update-ytdlp
curl -s http://127.0.0.1/api/v1/version | jq
```

To pin a known-good release or test `nightly`:
```dotenv
# In .env.prod:
YTDLP_CHANNEL=nightly
# or:
YTDLP_PINNED_VERSION=2026.10.26
```
Then run `make update-ytdlp`.

---

## 2. Reading Structured JSON Logs

All API and worker logs emit newline-delimited JSON with automatic credential/token/cookie redaction and `request_id` correlation:

```bash
# Follow live production logs
make prod-logs

# Filter failed jobs with jq
docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod logs api worker --no-log-prefix \
  | jq -R 'fromjson? | select(.level == "ERROR" or .level == "WARNING")'
```

---

## 3. Metrics & Dashboards (Prometheus + Grafana)

The API exposes Prometheus metrics on internal endpoint `http://api:8000/metrics` (blocked on public Nginx).

Key metrics:
- `vdl_resolve_requests_total{platform,status,cached}`
- `vdl_resolve_duration_seconds`
- `vdl_jobs_total{platform,status}`
- `vdl_job_duration_seconds`
- `vdl_extraction_failures_total{error_code,platform,proxy}`
- `vdl_queue_depth` / `vdl_active_jobs{platform}`
- `vdl_bytes_served_total{platform}`
- `vdl_canary_platform_up{platform}` (`1` = healthy, `0` = degraded)
- `vdl_cookie_valid{platform}` (`1` = valid, `0` = expired, `-1` = not configured)
- `vdl_storage_free_bytes`

Enable the bundled local-only Prometheus (port `127.0.0.1:9090`) and Grafana (`127.0.0.1:3001`) profile:
```bash
docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod --profile monitoring up -d
```
Tunnel over SSH (`ssh -L 3001:127.0.0.1:3001 user@vps`) to view Grafana securely without exposing it publicly.

### Recommended Alerts
1. `vdl_canary_platform_up == 0` for > 24h → Platform extractor broken or IP blocked.
2. `vdl_cookie_valid == 0` → Refresh expired cookie file in `secrets/cookies/<platform>.txt`.
3. `vdl_storage_free_bytes < 2e9` → Low disk space; inspect cleanup cron or reduce `FILE_TTL_SECONDS`.
4. `rate(vdl_extraction_failures_total{error_code="BOT_CHECK"}[15m]) > 0.2` → Rotate proxy pool or enable WARP.

---

## 4. Storage Cleanup & Disk Quota

- Completed files automatically expire after `FILE_TTL_SECONDS` (default 30 min) and are purged every 10 minutes by `cleanup_expired_files_cron`.
- Active temp working directories live on `tmpfs` (`/tmp/vdl`), keeping SSD wear minimal and remuxing fast.
- If free space drops below `MIN_FREE_DISK_BYTES`, new jobs are refused cleanly with HTTP 507 (`DISK_FULL`).

---

## 5. Scaling Workers

Horizontal scaling is built in via Redis + `arq`:
```bash
docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod up -d --scale worker=3
```
Tune `WORKER_CONCURRENCY` (jobs per worker) and `PER_PLATFORM_CONCURRENCY` (semaphore per host) in `.env.prod` based on your VPS CPU cores and egress bandwidth.

---

## 6. Routine Checks

```bash
make smoke          # Real-world end-to-end check per platform + ffprobe verification
make bench          # Measure resolve latency, TTFB, total time, and MB/s
make cookies-check  # Validate mounted Netscape cookies
make audit          # Run pip-audit + npm audit vulnerability checks
```
