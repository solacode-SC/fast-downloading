#!/usr/bin/env bash
set -euo pipefail

# =====================================================================
# FastDL Turnkey VPS Production Provisioning Script
# Default Domain : fastdownloading.solaymanbuilds.com
# Default Email  : elmouden00den@gmail.com
# =====================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DOMAIN="${DOMAIN:-fastdownloading.solaymanbuilds.com}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-elmouden00den@gmail.com}"
NETWORK_MODE="${NETWORK_MODE:-bundled}"   # "bundled" (ports 80/443 + Certbot) or "external" (proxy_net)
EXTERNAL_NET="${EXTERNAL_NET:-proxy_net}"
SKIP_SSL="${SKIP_SSL:-false}"
ENABLE_WARP="${ENABLE_WARP:-false}"

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

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    return 1
  fi
}

echo -e "${GREEN}=================================================================${RESET}"
echo -e "${GREEN}  FastDL VPS Production Setup${RESET}"
echo -e "  Domain       : ${CYAN}${DOMAIN}${RESET}"
echo -e "  Email        : ${CYAN}${LETSENCRYPT_EMAIL}${RESET}"
echo -e "  Network Mode : ${CYAN}${NETWORK_MODE}${RESET}"
echo -e "${GREEN}=================================================================${RESET}"

# ------------------------------------------------------------------
# 1. Host Prerequisites (Packages, Docker, Swap, Firewall)
# ------------------------------------------------------------------
log_step "1/5 Checking VPS host prerequisites (Docker, tools, swap, firewall)..."

if command -v apt-get >/dev/null 2>&1; then
  MISSING_PKGS=()
  for bin_pkg in "curl:curl" "git:git" "jq:jq" "openssl:openssl"; do
    bin="${bin_pkg%%:*}"
    pkg="${bin_pkg##*:}"
    if ! command -v "$bin" >/dev/null 2>&1; then
      MISSING_PKGS+=("$pkg")
    fi
  done
  if [ "${#MISSING_PKGS[@]}" -gt 0 ]; then
    echo "Installing missing host packages: ${MISSING_PKGS[*]}..."
    run_root apt-get update -qq && run_root apt-get install -y -qq ca-certificates "${MISSING_PKGS[@]}" || log_warn "Could not install packages automatically"
  fi
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Installing Docker Engine..."
  curl -fsSL https://get.docker.com | run_root sh
  run_root systemctl enable --now docker || true
  if [ "$(id -u)" -ne 0 ] && [ -n "${USER:-}" ]; then
    run_root usermod -aG docker "$USER" || true
  fi
fi

if ! docker compose version >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    run_root apt-get update -qq && run_root apt-get install -y -qq docker-compose-plugin || true
  fi
fi

docker compose version >/dev/null 2>&1 || {
  echo -e "${RED}ERROR: 'docker compose' v2 plugin is required.${RESET}" >&2
  exit 1
}
log_ok "Docker and Docker Compose are available."

# Ensure at least 2 GiB swap on small VPS nodes so Next.js image builds never OOM
if [ -f /proc/swaps ] && [ "$(wc -l < /proc/swaps)" -le 1 ] && [ ! -f /swapfile ]; then
  if [ "$(id -u)" -eq 0 ] || (command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null); then
    echo "Configuring 2 GiB swapfile (/swapfile) for build stability..."
    (run_root fallocate -l 2G /swapfile || run_root dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none) && \
      run_root chmod 600 /swapfile && \
      run_root mkswap /swapfile >/dev/null && \
      run_root swapon /swapfile && \
      (grep -q '/swapfile' /etc/fstab 2>/dev/null || echo '/swapfile none swap sw 0 0' | run_root tee -a /etc/fstab >/dev/null) && \
      log_ok "2 GiB swap enabled." || log_warn "Skipping swapfile creation (insufficient permissions or unsupported filesystem)."
  fi
fi

# Configure UFW firewall ports if UFW is active in bundled mode
if [ "$NETWORK_MODE" = "bundled" ] && command -v ufw >/dev/null 2>&1; then
  if run_root ufw status 2>/dev/null | grep -q "Status: active"; then
    run_root ufw allow 22/tcp >/dev/null || true
    run_root ufw allow 80/tcp >/dev/null || true
    run_root ufw allow 443/tcp >/dev/null || true
    log_ok "UFW firewall rules verified (22/tcp, 80/tcp, 443/tcp)."
  fi
fi

# ------------------------------------------------------------------
# 2. Environment & Secrets Bootstrap
# ------------------------------------------------------------------
log_step "2/5 Configuring .env.prod for ${DOMAIN} (${LETSENCRYPT_EMAIL})..."

FORCE_DOMAIN="$DOMAIN" FORCE_EMAIL="$LETSENCRYPT_EMAIL" DOMAIN="$DOMAIN" LETSENCRYPT_EMAIL="$LETSENCRYPT_EMAIL" bash scripts/setup.sh

# Ensure external proxy network exists
docker network inspect "$EXTERNAL_NET" >/dev/null 2>&1 || docker network create "$EXTERNAL_NET" >/dev/null
log_ok ".env.prod, secrets/cookies/, and Docker network '${EXTERNAL_NET}' are ready."

# ------------------------------------------------------------------
# 3. Build & Start Production Stack
# ------------------------------------------------------------------
log_step "3/5 Building and launching FastDL production stack (vdl-prod)..."

COMPOSE_ARGS=(-p vdl-prod -f docker-compose.prod.yml)
if [ "$NETWORK_MODE" = "external" ]; then
  COMPOSE_ARGS+=(-f docker-compose.prod.external-net.yml)
  # Ensure external-proxy-snippet.conf has the configured domain
  if [ -f nginx/conf.d/external-proxy-snippet.conf ]; then
    sed -i.bak "s/server_name .*/server_name ${DOMAIN};/g" nginx/conf.d/external-proxy-snippet.conf && rm -f nginx/conf.d/external-proxy-snippet.conf.bak
    sed -i.bak "s|/etc/letsencrypt/live/[^/]*/|/etc/letsencrypt/live/${DOMAIN}/|g" nginx/conf.d/external-proxy-snippet.conf && rm -f nginx/conf.d/external-proxy-snippet.conf.bak
  fi
fi
COMPOSE_ARGS+=(--env-file .env.prod)

if [ "$ENABLE_WARP" = "true" ]; then
  COMPOSE_ARGS+=(--profile warp)
fi

IMAGE_TAG=latest docker compose "${COMPOSE_ARGS[@]}" build --pull || IMAGE_TAG=latest docker compose "${COMPOSE_ARGS[@]}" build
IMAGE_TAG=latest docker compose "${COMPOSE_ARGS[@]}" up -d --remove-orphans --wait

log_ok "All production containers are up and healthy."

# ------------------------------------------------------------------
# 4. Automated Let's Encrypt SSL/TLS Provisioning
# ------------------------------------------------------------------
log_step "4/5 Configuring HTTPS / TLS for ${DOMAIN}..."

SSL_ACTIVE="false"
if [ "$NETWORK_MODE" = "external" ]; then
  log_ok "External Nginx mode active (zero host ports published)."
  echo "  Include 'nginx/conf.d/external-proxy-snippet.conf' in your host Nginx container connected to '${EXTERNAL_NET}'."
elif [ "$SKIP_SSL" = "true" ]; then
  log_warn "SKIP_SSL=true set; skipping Let's Encrypt certificate request. Run 'make ssl-setup' when ready."
else
  if DOMAIN="$DOMAIN" LETSENCRYPT_EMAIL="$LETSENCRYPT_EMAIL" bash scripts/ssl_setup.sh issue; then
    SSL_ACTIVE="true"
    log_ok "Let's Encrypt TLS certificate active and auto-renewal cron installed for ${DOMAIN}."
  else
    log_warn "Let's Encrypt certificate issuance did not succeed yet (ensure DNS A record for ${DOMAIN} points to this VPS IP and port 80 is reachable)."
    echo -e "  The app is running over HTTP now. Once DNS propagates, run: ${CYAN}make ssl-setup${RESET}"
  fi
fi

# ------------------------------------------------------------------
# 5. Final Verification & Summary
# ------------------------------------------------------------------
log_step "5/5 Verifying production health endpoints..."

NGINX_HTTP_PORT="$(grep -E '^NGINX_HTTP_PORT=' .env.prod 2>/dev/null | head -n1 | cut -d= -f2- || echo "80")"
LOCAL_CHECK_URL="http://127.0.0.1:${NGINX_HTTP_PORT:-80}"

if [ "$NETWORK_MODE" = "bundled" ]; then
  if curl -fsS "${LOCAL_CHECK_URL}/healthz" >/dev/null 2>&1; then
    log_ok "Local Nginx -> API healthz check passed (${LOCAL_CHECK_URL}/healthz)."
  else
    log_warn "Local healthz probe returned non-200 at ${LOCAL_CHECK_URL}/healthz"
  fi
fi

if [ "$SSL_ACTIVE" = "true" ]; then
  if curl -fsS "https://${DOMAIN}/healthz" >/dev/null 2>&1; then
    log_ok "Public HTTPS check passed (https://${DOMAIN}/healthz)."
  fi
fi

echo ""
echo -e "${GREEN}=================================================================${RESET}"
echo -e "${GREEN}  FastDL Production Stack Ready!${RESET}"
echo -e "  Public URL   : ${CYAN}https://${DOMAIN}${RESET}"
echo -e "  Cert Email   : ${CYAN}${LETSENCRYPT_EMAIL}${RESET}"
echo -e "  Update App   : ${CYAN}make update${RESET}"
echo -e "  Check Status : ${CYAN}make prod-ps${RESET}"
echo -e "  Live Logs    : ${CYAN}make prod-logs${RESET}"
echo -e "  Renew SSL    : ${CYAN}make ssl-renew${RESET}"
echo -e "${GREEN}=================================================================${RESET}"
