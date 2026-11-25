#!/usr/bin/env bash
set -euo pipefail

# =====================================================================
# FastDL Automated Production Pull & Update Script
# - Tags current images as :previous for instant rollback
# - Pulls latest git commits (--ff-only) and shows changelog
# - Syncs any new .env.prod.example keys into .env.prod safely
# - Rebuilds images, performs rolling update with healthcheck wait
# - Reloads Nginx and auto-rolls back to :previous if healthcheck fails
# =====================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_SMOKE="${RUN_SMOKE:-false}"
UPDATE_YTDLP="${UPDATE_YTDLP:-false}"
for arg in "$@"; do
  case "$arg" in
    --smoke) RUN_SMOKE="true" ;;
    --update-ytdlp) UPDATE_YTDLP="true" ;;
  esac
done

CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

log_step() {
  echo -e "\n${CYAN}==> $1${RESET}"
}

log_ok() {
  echo -e "${GREEN}[OK]${RESET} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${RESET} $1"
}

echo -e "${GREEN}=================================================================${RESET}"
echo -e "${GREEN}  FastDL Production Pull & Update${RESET}"
echo -e "${GREEN}=================================================================${RESET}"

# ------------------------------------------------------------------
# 1. Tag current images as :previous for safety rollback
# ------------------------------------------------------------------
log_step "1/5 Tagging current production images as ':previous'..."

HAVE_PREVIOUS="false"
if docker image inspect vdl-backend:latest >/dev/null 2>&1 && docker image inspect vdl-frontend:latest >/dev/null 2>&1; then
  docker tag vdl-backend:latest vdl-backend:previous
  docker tag vdl-frontend:latest vdl-frontend:previous
  HAVE_PREVIOUS="true"
  log_ok "Tagged vdl-backend:previous and vdl-frontend:previous."
else
  log_warn "No existing :latest images found to tag as :previous (first build)."
fi

# ------------------------------------------------------------------
# 2. Pull latest code from Git repository
# ------------------------------------------------------------------
log_step "2/5 Pulling latest code from Git..."

OLD_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo "none")"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")"

if git remote get-url origin >/dev/null 2>&1; then
  git fetch origin "$CURRENT_BRANCH" --prune || git fetch --all --prune || log_warn "git fetch failed; proceeding with local checkout"
  if git pull --ff-only origin "$CURRENT_BRANCH" 2>/dev/null || git pull --ff-only 2>/dev/null; then
    NEW_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo "none")"
    if [ "$OLD_COMMIT" != "$NEW_COMMIT" ]; then
      log_ok "Updated git commit: ${OLD_COMMIT} -> ${NEW_COMMIT}"
      echo "Recent commits:"
      git log --oneline "${OLD_COMMIT}..${NEW_COMMIT}" | sed 's/^/  /'
    else
      log_ok "Already up to date at commit ${NEW_COMMIT}."
    fi
  else
    log_warn "git pull --ff-only could not fast-forward (local modifications present); building from working tree (${OLD_COMMIT})."
  fi
else
  log_warn "No 'origin' git remote configured; building from current working tree (${OLD_COMMIT})."
fi

# ------------------------------------------------------------------
# 3. Sync environment files & detect active deployment topology
# ------------------------------------------------------------------
log_step "3/5 Syncing .env.prod configuration..."

bash scripts/setup.sh

# Auto-detect whether external-net mode or optional profiles are active
NETWORK_MODE="${NETWORK_MODE:-auto}"
if [ "$NETWORK_MODE" = "auto" ]; then
  if docker ps --format '{{.Names}}' | grep -q '^vdl-prod-api' && ! docker ps --format '{{.Names}}' | grep -q '^vdl-prod-nginx'; then
    NETWORK_MODE="external"
  else
    NETWORK_MODE="bundled"
  fi
fi

COMPOSE_ARGS=(-p vdl-prod -f docker-compose.prod.yml)
if [ "$NETWORK_MODE" = "external" ]; then
  COMPOSE_ARGS+=(-f docker-compose.prod.external-net.yml)
fi
COMPOSE_ARGS+=(--env-file .env.prod)

for profile_svc in "warp:vdl-prod-warp" "proxy:vdl-prod-proxy" "monitoring:vdl-prod-prometheus"; do
  prof="${profile_svc%%:*}"
  cname="${profile_svc##*:}"
  if docker ps --format '{{.Names}}' | grep -q "^${cname}"; then
    COMPOSE_ARGS+=(--profile "$prof")
  fi
done

log_ok "Target stack: vdl-prod (mode: ${NETWORK_MODE})"

# ------------------------------------------------------------------
# 4. Build updated images & perform rolling update
# ------------------------------------------------------------------
log_step "4/5 Building production images and rolling out update..."

rollback_on_failure() {
  echo -e "\n${RED}ERROR: Update failed!${RESET}" >&2
  if [ "$HAVE_PREVIOUS" = "true" ]; then
    echo -e "${YELLOW}Auto-rolling back to ':previous' production images...${RESET}" >&2
    IMAGE_TAG=previous docker compose "${COMPOSE_ARGS[@]}" up -d --wait || true
    if [ "$NETWORK_MODE" = "bundled" ] && docker ps --format '{{.Names}}' | grep -q '^vdl-prod-nginx'; then
      docker compose "${COMPOSE_ARGS[@]}" exec -T nginx nginx -s reload >/dev/null 2>&1 || true
    fi
    echo -e "${YELLOW}Rollback to ':previous' complete.${RESET}" >&2
  fi
  exit 1
}

if ! (IMAGE_TAG=latest docker compose "${COMPOSE_ARGS[@]}" build --pull || IMAGE_TAG=latest docker compose "${COMPOSE_ARGS[@]}" build); then
  rollback_on_failure
fi

# Remove any failed vdl-prod-nginx container from an earlier port-80 conflict before recreating
if [ "$NETWORK_MODE" = "bundled" ] && docker ps -a --format '{{.Names}} {{.Status}}' | grep '^vdl-prod-nginx' | grep -qv 'Up'; then
  docker rm -f vdl-prod-nginx-1 >/dev/null 2>&1 || true
fi

if ! IMAGE_TAG=latest docker compose "${COMPOSE_ARGS[@]}" up -d --remove-orphans --wait; then
  rollback_on_failure
fi
# Ensure Cloudflare WARP sidecar is started for datacenter IP anti-block fallback (non-fatal if kernel lacks tun)
IMAGE_TAG=latest docker compose "${COMPOSE_ARGS[@]}" --profile warp up -d warp >/dev/null 2>&1 || true

# Reload Nginx config if bundled Nginx is running
if [ "$NETWORK_MODE" = "bundled" ] && docker ps --format '{{.Names}}' | grep -q '^vdl-prod-nginx'; then
  docker compose "${COMPOSE_ARGS[@]}" exec -T nginx nginx -t && \
    docker compose "${COMPOSE_ARGS[@]}" exec -T nginx nginx -s reload
  sleep 1
  log_ok "Nginx validated and reloaded."
fi

if [ "$UPDATE_YTDLP" = "true" ]; then
  bash scripts/update_ytdlp.sh prod || log_warn "Runtime yt-dlp overlay update skipped"
fi

# ------------------------------------------------------------------
# 5. Post-deploy health verification & image cleanup
# ------------------------------------------------------------------
log_step "5/5 Verifying updated services and cleaning dangling images..."

NGINX_HTTP_PORT="$(grep -E '^NGINX_HTTP_PORT=' .env.prod 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\r' || echo "8088")"
HEALTH_URL="http://127.0.0.1:${NGINX_HTTP_PORT:-8088}"

if [ "$NETWORK_MODE" = "bundled" ]; then
  HEALTH_OK="false"
  for attempt in $(seq 1 15); do
    if curl -fsS --max-time 5 "${HEALTH_URL}/healthz" >/dev/null 2>&1; then
      HEALTH_OK="true"
      break
    fi
    sleep 1
  done
  if [ "$HEALTH_OK" != "true" ]; then
    echo -e "${RED}Health check failed after 15 attempts (${HEALTH_URL}/healthz). Recent nginx logs:${RESET}" >&2
    docker compose "${COMPOSE_ARGS[@]}" logs --tail=20 nginx >&2 || true
    rollback_on_failure
  fi
  VERSION_INFO="$(curl -fsS --max-time 5 "${HEALTH_URL}/api/v1/version" 2>/dev/null || echo "{}")"
else
  HEALTH_OK="false"
  for attempt in $(seq 1 15); do
    if docker compose "${COMPOSE_ARGS[@]}" exec -T api curl -fsS --max-time 5 http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
      HEALTH_OK="true"
      break
    fi
    sleep 1
  done
  if [ "$HEALTH_OK" != "true" ]; then
    rollback_on_failure
  fi
  VERSION_INFO="$(docker compose "${COMPOSE_ARGS[@]}" exec -T api curl -fsS --max-time 5 http://127.0.0.1:8000/api/v1/version 2>/dev/null || echo "{}")"
fi

log_ok "Health check passed! Active version: ${VERSION_INFO}"

docker image prune -f >/dev/null 2>&1 || true

if [ "$RUN_SMOKE" = "true" ] && [ "$NETWORK_MODE" = "bundled" ]; then
  API_BASE_URL="$HEALTH_URL" bash scripts/smoke.sh
fi

DOMAIN="$(grep -E '^DOMAIN=' .env.prod 2>/dev/null | head -n1 | cut -d= -f2- || echo "fastdownloading.solaymanbuilds.com")"
echo ""
echo -e "${GREEN}=================================================================${RESET}"
echo -e "${GREEN}  FastDL Update Complete! (${OLD_COMMIT} -> $(git rev-parse --short HEAD 2>/dev/null || echo "latest"))${RESET}"
echo -e "  Domain : ${CYAN}https://${DOMAIN}${RESET}"
echo -e "${GREEN}=================================================================${RESET}"
