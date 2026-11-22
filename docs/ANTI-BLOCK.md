# Anti-Block & Reliability Architecture (Layers L1–L8)

Platforms routinely update bot defenses and rate limits. FastDL implements **8 independent, observable, env-configurable layers** so failures degrade gracefully with clear user-facing hints.

## Layer Overview

### L1 — Always-Current Extractors
- `yt-dlp` is installed from PyPI (`yt-dlp[default,curl-cffi]`) and supports runtime updates into a dedicated writable volume mounted at `/var/lib/vdl/ytdlp-overlay` (prepended to `PYTHONPATH`), preserving `read_only: true` on the root filesystem.
- **Automatic updates:** Run on production worker startup and daily at 03:15 UTC via arq cron, or on demand via `make update-ytdlp`.
- **Self-test & rollback:** Updates stage into a temporary directory, run an isolated subprocess import + extractor check (`Youtube`, `Twitter`, `Instagram`, `Facebook`), and atomically swap only on pass. If the self-test fails, the previous version remains untouched.
- **Controls:** `YTDLP_AUTO_UPDATE=true|false`, `YTDLP_CHANNEL=stable|nightly`, `YTDLP_PINNED_VERSION=2026.x.y`. Active version is exposed at `GET /api/v1/version`.

### L2 — Browser-Like Network Fingerprint (`curl_cffi`)
- Uses `yt-dlp`'s native `ImpersonateTarget` backed by `curl_cffi` (`IMPERSONATE_ENABLED=true`, `IMPERSONATE_TARGET=chrome`) to match real Chrome TLS JA3/JA4 + HTTP/2 fingerprints on Instagram, Facebook, X, and YouTube web clients.
- Intentionally avoids injecting a custom `User-Agent` header that would contradict the impersonated TLS fingerprint; only sets a realistic `Accept-Language: en-US,en;q=0.9`.

### L3 — YouTube PO Tokens & `player_client` Fallback
- Runs `brainicism/bgutil-ytdlp-pot-provider` as a sidecar container on internal port `4416`, wired into `yt-dlp` via `extractor_args["youtubepot-bgutilhttp"]["base_url"]`.
- Rotates automatically across `YOUTUBE_PLAYER_CLIENTS` (default: `default,web_safari,tv,mweb,android_vr`) whenever a client fails with a retryable/anti-bot error or yields zero usable formats.

### L4 — Optional User-Supplied Cookies (Hot-Reloaded)
- Mount Netscape-format cookie files at `secrets/cookies/{youtube,x,instagram,facebook}.txt` (mapped read-only to `/run/secrets/cookies/` inside containers).
- **Important:** Only use a dedicated throwaway account. Never commit cookie files to git (`secrets/` is in `.gitignore`).
- **Hot-reload:** `CookieManager` watches file `mtime` on each use; replacing a file immediately clears any previous expired flag without restarting containers.
- **Expiry detection:** Auth failures with cookies mark that platform's cookies as `expired` in `GET /readyz` and set Prometheus gauge `vdl_cookie_valid{platform="..."}` to `0`.
- Validate locally anytime with `make cookies-check`.

### L5 — Egress IP Strategy & Proxy Pool
- Configure `PROXY_URLS` (comma-separated `http://`, `https://`, `socks5://`, `socks5h://`) or per-platform overrides (`PROXY_URLS_YOUTUBE`, `PROXY_URLS_INSTAGRAM`, etc.).
- Supports `sticky` (consistent hash per job) or `round_robin` selection.
- Automatically ejects proxies after `PROXY_MAX_FAILURES` consecutive failures for `PROXY_COOLDOWN_SECONDS`, then re-admits them automatically.
- See [EGRESS.md](EGRESS.md) for residential proxies, Cloudflare WARP sidecar (`--profile warp`), and home/ISP worker tunneling.

### L6 — Polite Traffic Shaping & Circuit Breakers
- Redis sliding-window rate limits per IP (`RATE_LIMIT_RESOLVE_PER_MINUTE`, `RATE_LIMIT_JOBS_PER_MINUTE`), concurrent active job caps per IP (`MAX_CONCURRENT_JOBS_PER_IP`), and per-platform rate limits (`PLATFORM_RATE_LIMIT_PER_MINUTE`).
- Per-platform worker semaphores prevent one slow upstream from starving others.
- Random jittered pre-request delays (`JITTER_MIN_MS`..`JITTER_MAX_MS`) and exponential backoff on retries.
- Per-(platform, proxy) Redis circuit breaker trips open after `CIRCUIT_BREAKER_THRESHOLD` anti-bot/429 hits and returns `CIRCUIT_OPEN` with `"Please try again in N seconds."`.

### L7 — Typed Error Classification, Escalation & Daily Canary
- Raw `yt-dlp` errors are classified into typed codes: `BOT_CHECK`, `LOGIN_REQUIRED`, `AGE_RESTRICTED`, `GEO_BLOCKED`, `PRIVATE`, `REMOVED`, `LIVE_STREAM`, `DRM_PROTECTED`, `RATE_LIMITED`, `UNSUPPORTED`, `NETWORK`.
- Non-retryable errors (`PRIVATE`, `REMOVED`, `AGE_RESTRICTED`, `DRM_PROTECTED`, `LIVE_STREAM`) fail immediately with clear messages.
- Retryable errors escalate automatically: next `player_client` → alternate healthy proxy → platform cookies (if configured) → fail cleanly.
- Daily canary cron (`04:00 UTC`) resolves one public URL per platform, exports `vdl_canary_platform_up` and `vdl_canary_latency_seconds` to Prometheus, and logs a `CANARY ALERT` on degradation.

### L8 — Observability
- Structured JSON logs with automatic redaction of proxy credentials, signed tokens, and cookies.
- Request ID correlation (`X-Request-ID`).
- Prometheus `/metrics` (internal only, blocked on public Nginx) + optional Grafana stack (`--profile monitoring`) + optional Sentry (`SENTRY_DSN`).

---

## Debugging a Blocked Platform

1. **Check `/readyz`:**
   ```bash
   curl -s http://127.0.0.1/readyz | jq
   ```
   Verify `pot_provider: true`, `cookies` status (`valid` vs `expired`), and `proxies_healthy`.
2. **Check error breakdown in Prometheus / logs:**
   ```bash
   make prod-logs | grep -E 'BOT_CHECK|LOGIN_REQUIRED|RATE_LIMITED'
   ```
3. **Update `yt-dlp` first:**
   ```bash
   make update-ytdlp
   ```
   If stable hasn't picked up a breaking platform change yet, switch `YTDLP_CHANNEL=nightly` in `.env.prod` and run `make update-ytdlp`.
4. **Test with WARP or a residential proxy:**
   See [EGRESS.md](EGRESS.md).
5. **Refresh cookies (Instagram / Facebook / age-gated YouTube):**
   Export fresh Netscape cookies from a throwaway session to `secrets/cookies/<platform>.txt` and run `make cookies-check`.
