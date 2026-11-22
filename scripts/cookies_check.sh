#!/usr/bin/env bash
set -euo pipefail

COOKIES_DIR="${COOKIES_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/secrets/cookies}"
echo "Checking Netscape cookies in: $COOKIES_DIR"
echo ""

printf "%-12s | %-16s | %s\n" "PLATFORM" "STATUS" "DETAIL"
printf "%-12s-+-%-16s-+-%s\n" "------------" "----------------" "------------------------------------"

for platform in youtube x instagram facebook; do
  FILE="$COOKIES_DIR/${platform}.txt"
  if [ ! -f "$FILE" ]; then
    printf "%-12s | %-16s | %s\n" "$platform" "NOT_CONFIGURED" "Direct anonymous extraction active"
    continue
  fi
  ENTRIES="$(grep -vE '^(#[^H]|$)' "$FILE" | awk -F'\t' 'NF >= 7 {count++} END {print count+0}')"
  if [ "$ENTRIES" -gt 0 ]; then
    printf "%-12s | %-16s | %s\n" "$platform" "VALID_FORMAT" "${ENTRIES} cookie entries found"
  else
    printf "%-12s | %-16s | %s\n" "$platform" "INVALID_FORMAT" "Expected tab-separated Netscape format"
  fi
done
