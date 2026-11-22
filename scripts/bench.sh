#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
URLS_FILE="${URLS_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smoke_urls.txt}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "=== FastDL Speed Benchmark ==="
echo "Target API: $API_BASE_URL"
echo ""

printf "%-12s | %-10s | %-10s | %-10s | %-10s | %-10s\n" \
  "PLATFORM" "RESOLVE" "JOB_TIME" "TTFB" "AVG_MB/S" "SIZE_MB"
printf "%-12s-+-%-10s-+-%-10s-+-%-10s-+-%-10s-+-%-10s\n" \
  "------------" "----------" "----------" "----------" "----------" "----------"

while IFS='|' read -r platform url; do
  [[ -z "$platform" || "$platform" =~ ^# ]] && continue

  T0="$(date +%s.%N)"
  RES_HTTP="$(curl -sS -o "$TMP_DIR/${platform}_res.json" -w "%{http_code}" \
    -X POST "$API_BASE_URL/api/v1/resolve" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$url\"}")"
  T1="$(date +%s.%N)"
  RESOLVE_S="$(awk "BEGIN {printf \"%.2fs\", $T1 - $T0}")"

  if [ "$RES_HTTP" != "200" ]; then
    ERR_CODE="$(jq -r '.error.code // "ERR"' "$TMP_DIR/${platform}_res.json" 2>/dev/null || echo "HTTP_$RES_HTTP")"
    printf "%-12s | %-10s | %-10s | %-10s | %-10s | %-10s\n" "$platform" "$ERR_CODE" "-" "-" "-" "-"
    continue
  fi

  TJ0="$(date +%s.%N)"
  JOB_ID="$(curl -fsS -X POST "$API_BASE_URL/api/v1/jobs" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$url\",\"preset\":\"best\"}" | jq -r '.job_id')"

  STATUS="queued"
  for _ in $(seq 1 120); do
    curl -fsS "$API_BASE_URL/api/v1/jobs/$JOB_ID" > "$TMP_DIR/${platform}_snap.json"
    STATUS="$(jq -r '.status' "$TMP_DIR/${platform}_snap.json")"
    if [[ "$STATUS" == "ready" || "$STATUS" == "failed" ]]; then
      break
    fi
    sleep 0.5
  done
  TJ1="$(date +%s.%N)"
  JOB_S="$(awk "BEGIN {printf \"%.2fs\", $TJ1 - $TJ0}")"

  if [ "$STATUS" != "ready" ]; then
    ERR_CODE="$(jq -r '.error.code // "FAIL"' "$TMP_DIR/${platform}_snap.json")"
    printf "%-12s | %-10s | %-10s | %-10s | %-10s | %-10s\n" "$platform" "$RESOLVE_S" "$ERR_CODE" "-" "-" "-"
    continue
  fi

  DL_URL="$(jq -r '.download_url' "$TMP_DIR/${platform}_snap.json")"
  METRICS="$(curl -sS -o /dev/null -w "%{time_starttransfer} %{time_total} %{size_download}" "${API_BASE_URL}${DL_URL}")"
  read -r TTFB TOTAL_T BYTES <<< "$METRICS"

  TOTAL_S="$(awk "BEGIN {t=($TJ1 - $TJ0) + $TOTAL_T; if (t<=0) t=0.01; printf \"%.3f\", t}")"
  SIZE_MB="$(awk "BEGIN {printf \"%.2f\", $BYTES / 1048576.0}")"
  AVG_MBPS="$(awk "BEGIN {printf \"%.2f\", ($BYTES / 1048576.0) / $TOTAL_S}")"
  TTFB_FMT="$(awk "BEGIN {printf \"%.3fs\", $TTFB}")"

  printf "%-12s | %-10s | %-10s | %-10s | %-10s | %-10s\n" \
    "$platform" "$RESOLVE_S" "$JOB_S" "$TTFB_FMT" "$AVG_MBPS" "$SIZE_MB"
done < "$URLS_FILE"
