#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
URLS_FILE="${URLS_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smoke_urls.txt}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "=== FastDL Real-World Smoke Test ==="
echo "Target API: $API_BASE_URL"
echo ""

# Basic system checks
curl -fsS "$API_BASE_URL/healthz" >/dev/null
echo "Healthz: OK"
VERSION_JSON="$(curl -fsS "$API_BASE_URL/api/v1/version")"
echo "Version: $VERSION_JSON"
echo ""

printf "%-12s | %-10s | %-10s | %-12s | %s\n" "PLATFORM" "RESOLVE" "DOWNLOAD" "FFPROBE" "DETAILS"
printf "%-12s-+-%-10s-+-%-10s-+-%-12s-+-%s\n" "------------" "----------" "----------" "------------" "----------------------------------------"

PASS_COUNT=0
BLOCKED_COUNT=0
FAIL_COUNT=0

while IFS='|' read -r platform url; do
  [[ -z "$platform" || "$platform" =~ ^# ]] && continue

  # 1. Resolve
  RES_HTTP="$(curl -sS -o "$TMP_DIR/${platform}_res.json" -w "%{http_code}" \
    -X POST "$API_BASE_URL/api/v1/resolve" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$url\"}")"

  if [ "$RES_HTTP" != "200" ]; then
    ERR_CODE="$(jq -r '.error.code // "UNKNOWN"' "$TMP_DIR/${platform}_res.json" 2>/dev/null || echo "HTTP_$RES_HTTP")"
    ERR_MSG="$(jq -r '.error.message // "Resolve failed"' "$TMP_DIR/${platform}_res.json" 2>/dev/null || echo "Resolve failed")"
    if [[ "$ERR_CODE" =~ ^(BOT_CHECK|LOGIN_REQUIRED|RATE_LIMITED|GEO_BLOCKED|CIRCUIT_OPEN|REMOVED|NETWORK)$ ]]; then
      printf "%-12s | %-10s | %-10s | %-12s | %s\n" "$platform" "BLOCKED" "SKIP" "SKIP" "[$ERR_CODE] $ERR_MSG"
      BLOCKED_COUNT=$((BLOCKED_COUNT + 1))
    else
      printf "%-12s | %-10s | %-10s | %-12s | %s\n" "$platform" "FAIL" "SKIP" "SKIP" "[$ERR_CODE] $ERR_MSG"
      FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    continue
  fi

  RES_MS="$(jq -r '.resolve_ms // 0' "$TMP_DIR/${platform}_res.json")"
  FMT_CNT="$(jq -r '.formats | length' "$TMP_DIR/${platform}_res.json")"

  # 2. Create download job
  JOB_HTTP="$(curl -sS -o "$TMP_DIR/${platform}_job.json" -w "%{http_code}" \
    -X POST "$API_BASE_URL/api/v1/jobs" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$url\",\"preset\":\"best\"}")"

  if [ "$JOB_HTTP" != "202" ]; then
    ERR_CODE="$(jq -r '.error.code // "JOB_ERR"' "$TMP_DIR/${platform}_job.json" 2>/dev/null || echo "HTTP_$JOB_HTTP")"
    printf "%-12s | %-10s | %-10s | %-12s | %s\n" "$platform" "OK(${RES_MS}ms)" "FAIL" "SKIP" "Job create failed [$ERR_CODE]"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    continue
  fi

  JOB_ID="$(jq -r '.job_id' "$TMP_DIR/${platform}_job.json")"

  # 3. Poll until terminal state (max 90s)
  STATUS="queued"
  for _ in $(seq 1 90); do
    curl -sS "$API_BASE_URL/api/v1/jobs/$JOB_ID" > "$TMP_DIR/${platform}_snap.json"
    STATUS="$(jq -r '.status' "$TMP_DIR/${platform}_snap.json")"
    if [[ "$STATUS" == "ready" || "$STATUS" == "failed" || "$STATUS" == "cancelled" ]]; then
      break
    fi
    sleep 1
  done

  if [ "$STATUS" != "ready" ]; then
    ERR_CODE="$(jq -r '.error.code // "TIMEOUT"' "$TMP_DIR/${platform}_snap.json" 2>/dev/null || echo "TIMEOUT")"
    ERR_MSG="$(jq -r '.error.message // "Download did not finish"' "$TMP_DIR/${platform}_snap.json" 2>/dev/null || echo "Timeout")"
    if [[ "$ERR_CODE" =~ ^(BOT_CHECK|LOGIN_REQUIRED|RATE_LIMITED|GEO_BLOCKED|CIRCUIT_OPEN|NETWORK)$ ]]; then
      printf "%-12s | %-10s | %-10s | %-12s | %s\n" "$platform" "OK(${RES_MS}ms)" "BLOCKED" "SKIP" "[$ERR_CODE] $ERR_MSG"
      BLOCKED_COUNT=$((BLOCKED_COUNT + 1))
    else
      printf "%-12s | %-10s | %-10s | %-12s | %s\n" "$platform" "OK(${RES_MS}ms)" "FAIL" "SKIP" "[$ERR_CODE] $ERR_MSG"
      FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    continue
  fi

  # 4. Stream file & verify with ffprobe
  DL_URL="$(jq -r '.download_url' "$TMP_DIR/${platform}_snap.json")"
  OUT_FILE="$TMP_DIR/${platform}.media"
  curl -fsS "${API_BASE_URL}${DL_URL}" -o "$OUT_FILE"
  SIZE_BYTES="$(wc -c < "$OUT_FILE")"

  PROBE_INFO="no-ffprobe"
  if command -v ffprobe >/dev/null 2>&1; then
    STREAMS="$(ffprobe -v error -show_entries stream=codec_type,codec_name -of csv=p=0 "$OUT_FILE" | tr '\n' ',' | sed 's/,$//')"
    if [ -n "$STREAMS" ]; then
      PROBE_INFO="OK"
    else
      PROBE_INFO="EMPTY"
    fi
  fi

  printf "%-12s | %-10s | %-10s | %-12s | %s\n" \
    "$platform" "OK(${RES_MS}ms)" "OK" "$PROBE_INFO" "size=${SIZE_BYTES}B fmts=${FMT_CNT} streams=${STREAMS:-n/a}"
  PASS_COUNT=$((PASS_COUNT + 1))
done < "$URLS_FILE"

echo ""
echo "Summary: passed=$PASS_COUNT platform_blocked=$BLOCKED_COUNT failed=$FAIL_COUNT"
if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
