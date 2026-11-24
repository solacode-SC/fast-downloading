#!/usr/bin/env bash
set -euo pipefail

# =====================================================================
# FastDL Host Nginx Reverse-Proxy & Let's Encrypt Certbot Script
# Domain : fastdownloading.solaymanbuilds.com
# Email  : elmouden00den@gmail.com
# Upstream: http://127.0.0.1:${NGINX_HTTP_PORT:-8088}
# =====================================================================

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
APP_PORT="${NGINX_HTTP_PORT:-$(read_env_var NGINX_HTTP_PORT "8088")}"
NGINX_AVAILABLE="/etc/nginx/sites-available/${DOMAIN}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "ERROR: Root or sudo privileges are required to configure host Nginx & Certbot." >&2
    exit 1
  fi
}

ensure_host_nginx_and_certbot() {
  if ! command -v nginx >/dev/null 2>&1 || ! command -v certbot >/dev/null 2>&1; then
    echo "Installing host nginx, certbot, and python3-certbot-nginx..."
    run_root apt-get update -y
    run_root apt-get install -y nginx certbot python3-certbot-nginx
  fi
  run_root systemctl enable --now nginx
}

configure_host_nginx_vhost() {
  echo "Configuring host Nginx reverse proxy for ${DOMAIN} -> http://127.0.0.1:${APP_PORT}..."
  run_root mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

  run_root tee "$NGINX_AVAILABLE" >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    client_max_body_size 128k;

    # Server-Sent Events (SSE) live download progress: unbuffered
    location ~ ^/api/v1/jobs/[^/]+/events\$ {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_buffering off;
        proxy_cache off;
        gzip off;
        chunked_transfer_encoding on;
        proxy_read_timeout 1800s;
        proxy_send_timeout 1800s;
    }

    # Media file downloads: Range streaming & zero temp disk buffering
    location ^~ /api/v1/files/ {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Range \$http_range;
        proxy_set_header If-Range \$http_if_range;

        proxy_buffering off;
        proxy_request_buffering off;
        proxy_max_temp_file_size 0;
        gzip off;
        proxy_read_timeout 1800s;
        proxy_send_timeout 1800s;
    }

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 120s;
    }
}
EOF

  run_root ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED"
  run_root nginx -t
  run_root systemctl reload nginx
  echo "Host Nginx reverse proxy configured and reloaded."
}

case "$ACTION" in
  issue)
    echo "=== FastDL Host Nginx & Let's Encrypt TLS Setup ==="
    echo "Domain   : ${DOMAIN}"
    echo "Email    : ${LETSENCRYPT_EMAIL}"
    echo "Upstream : http://127.0.0.1:${APP_PORT}"
    echo ""

    ensure_host_nginx_and_certbot
    configure_host_nginx_vhost

    echo "Requesting/updating Let's Encrypt certificate via certbot --nginx..."
    if run_root certbot --nginx \
      -d "${DOMAIN}" \
      --non-interactive \
      --agree-tos \
      --no-eff-email \
      -m "${LETSENCRYPT_EMAIL}" \
      --redirect \
      --keep-until-expiring; then
      echo "SSL certificate installed and HTTPS redirect enabled for ${DOMAIN}!"
    else
      echo "WARNING: Certbot could not issue the SSL certificate yet." >&2
      echo "Ensure DNS A record for ${DOMAIN} points to this VPS IP, then re-run: make ssl-setup" >&2
      exit 1
    fi

    run_root systemctl enable --now certbot.timer >/dev/null 2>&1 || true
    run_root systemctl reload nginx
    echo "HTTPS is live at: https://${DOMAIN}"
    ;;

  renew)
    echo "=== Renewing Let's Encrypt TLS Certificates ==="
    run_root certbot renew --quiet
    run_root systemctl reload nginx
    echo "Certificates renewed and host Nginx reloaded."
    ;;

  *)
    echo "Usage: $0 {issue|renew}" >&2
    exit 1
    ;;
esac
