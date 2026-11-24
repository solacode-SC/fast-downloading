#!/usr/bin/env bash
set -euo pipefail

# Automated Let's Encrypt TLS certificate provisioning, Nginx HTTPS activation,
# and auto-renewal cron installer for FastDL production mode.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ACTION="${1:-issue}"

if [ ! -f .env.prod ]; then
  bash scripts/setup.sh
fi

read_env_var() {
  local key="$1"
  local fallback="$2"
  local val
  val="$(grep -E "^${key}=" .env.prod 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\r' || true)"
  echo "${val:-$fallback}"
}

DOMAIN="${DOMAIN:-$(read_env_var DOMAIN "fastdownloading.solaymanbuilds.com")}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$(read_env_var LETSENCRYPT_EMAIL "elmouden00den@gmail.com")}"
CERTBOT_STAGING="${CERTBOT_STAGING:-false}"

PROD_COMPOSE=(docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod)
CERTBOT_WWW_VOL="vdl-prod_vdl_prod_certbot_www"
LETSENCRYPT_VOL="vdl-prod_vdl_prod_letsencrypt"
TLS_CONF_PATH="nginx/conf.d/tls.local.conf"
TLS_TEMPLATE_PATH="nginx/templates/tls.conf.template"

render_tls_conf() {
  if [ ! -f "$TLS_TEMPLATE_PATH" ]; then
    echo "ERROR: Missing template $TLS_TEMPLATE_PATH" >&2
    exit 1
  fi
  sed "s/__DOMAIN__/${DOMAIN}/g" "$TLS_TEMPLATE_PATH" > "$TLS_CONF_PATH"
  echo "Rendered Nginx HTTPS config -> ${TLS_CONF_PATH} (domain: ${DOMAIN})"
}

reload_nginx() {
  if "${PROD_COMPOSE[@]}" exec -T nginx nginx -t; then
    "${PROD_COMPOSE[@]}" exec -T nginx nginx -s reload
    echo "Nginx configuration validated and reloaded."
  else
    echo "ERROR: Nginx configuration test failed! Rolling back ${TLS_CONF_PATH}..." >&2
    rm -f "$TLS_CONF_PATH"
    "${PROD_COMPOSE[@]}" exec -T nginx nginx -s reload || true
    exit 1
  fi
}

install_renewal_cron() {
  local cron_cmd="docker run --rm -v ${CERTBOT_WWW_VOL}:/var/www/certbot -v ${LETSENCRYPT_VOL}:/etc/letsencrypt certbot/certbot renew --webroot -w /var/www/certbot --quiet && docker compose -p vdl-prod -f ${ROOT_DIR}/docker-compose.prod.yml --env-file ${ROOT_DIR}/.env.prod exec -T nginx nginx -s reload >/dev/null 2>&1"
  local cron_schedule="15 3,15 * * *"

  if [ "$(id -u)" -eq 0 ] && [ -d /etc/cron.d ]; then
    cat > /etc/cron.d/fastdl-certbot <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
${cron_schedule} root ${cron_cmd}
EOF
    chmod 644 /etc/cron.d/fastdl-certbot
    echo "Installed system auto-renewal cron job at /etc/cron.d/fastdl-certbot"
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null && [ -d /etc/cron.d ]; then
    sudo tee /etc/cron.d/fastdl-certbot >/dev/null <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
${cron_schedule} root ${cron_cmd}
EOF
    sudo chmod 644 /etc/cron.d/fastdl-certbot
    echo "Installed system auto-renewal cron job at /etc/cron.d/fastdl-certbot"
  elif command -v crontab >/dev/null 2>&1; then
    local existing_cron
    existing_cron="$(crontab -l 2>/dev/null | grep -v 'vdl-prod_vdl_prod_letsencrypt' || true)"
    printf "%s\n%s %s\n" "$existing_cron" "$cron_schedule" "$cron_cmd" | sed '/^$/d' | crontab -
    echo "Installed user crontab entry for twice-daily Let's Encrypt renewal."
  else
    echo "NOTE: cron is not installed; run 'make ssl-renew' periodically to renew certificates."
  fi
}

case "$ACTION" in
  issue)
    echo "=== FastDL Let's Encrypt TLS Provisioning ==="
    echo "Domain : ${DOMAIN}"
    echo "Email  : ${LETSENCRYPT_EMAIL}"
    echo ""

    # Ensure nginx is running so HTTP-01 challenge on port 80 works
    if ! docker ps --format '{{.Names}}' | grep -q '^vdl-prod-nginx'; then
      echo "Starting vdl-prod stack on HTTP first for ACME challenge..."
      "${PROD_COMPOSE[@]}" up -d
    fi

    STAGING_ARGS=()
    if [ "$CERTBOT_STAGING" = "true" ]; then
      STAGING_ARGS=(--staging)
      echo "Using Let's Encrypt STAGING environment..."
    fi

    docker run --rm \
      -v "${CERTBOT_WWW_VOL}:/var/www/certbot" \
      -v "${LETSENCRYPT_VOL}:/etc/letsencrypt" \
      certbot/certbot certonly --webroot \
      -w /var/www/certbot \
      -d "$DOMAIN" \
      --email "$LETSENCRYPT_EMAIL" \
      --agree-tos \
      --no-eff-email \
      --non-interactive \
      --keep-until-expiring \
      "${STAGING_ARGS[@]}"

    render_tls_conf
    reload_nginx
    install_renewal_cron
    echo ""
    echo "HTTPS is live at: https://${DOMAIN}"
    ;;

  renew)
    echo "=== Renewing Let's Encrypt TLS Certificates ==="
    docker run --rm \
      -v "${CERTBOT_WWW_VOL}:/var/www/certbot" \
      -v "${LETSENCRYPT_VOL}:/etc/letsencrypt" \
      certbot/certbot renew --webroot -w /var/www/certbot
    if [ -f "$TLS_CONF_PATH" ]; then
      reload_nginx
    fi
    ;;

  enable-existing)
    # Renders tls.local.conf and reloads Nginx if certificates already exist in the volume
    render_tls_conf
    reload_nginx
    ;;

  *)
    echo "Usage: $0 {issue|renew|enable-existing}" >&2
    exit 1
    ;;
esac
