#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEFAULT_DOMAIN="fastdownloading.solaymanbuilds.com"
DEFAULT_EMAIL="elmouden00den@gmail.com"

DOMAIN="${DOMAIN:-$DEFAULT_DOMAIN}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$DEFAULT_EMAIL}"

set_or_append_env() {
  local file="$1"
  local key="$2"
  local val="$3"
  if grep -qE "^${key}=" "$file" 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$file" && rm -f "${file}.bak"
  else
    printf "\n%s=%s\n" "$key" "$val" >> "$file"
  fi
}

sync_missing_env_keys() {
  local example_file="$1"
  local target_file="$2"
  while IFS= read -r line || [ -n "$line" ]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      if ! grep -qE "^${key}=" "$target_file" 2>/dev/null; then
        printf "%s\n" "$line" >> "$target_file"
        echo "Added new config key '${key}' to ${target_file}"
      fi
    fi
  done < "$example_file"
}

if [ ! -f .env.dev ]; then
  cp .env.dev.example .env.dev
  echo "Created .env.dev from .env.dev.example"
else
  sync_missing_env_keys .env.dev.example .env.dev
  echo ".env.dev already exists (kept and synced)"
fi

if [ ! -f .env.prod ]; then
  cp .env.prod.example .env.prod
  echo "Created .env.prod from .env.prod.example"
else
  sync_missing_env_keys .env.prod.example .env.prod
  echo ".env.prod already exists (kept and synced)"
fi

# Ensure DOMAIN, LETSENCRYPT_EMAIL, and CORS_ORIGINS are set properly in .env.prod
if ! grep -qE "^DOMAIN=" .env.prod || grep -qE "^DOMAIN=dl\.yourdomain\.com" .env.prod; then
  set_or_append_env .env.prod "DOMAIN" "$DOMAIN"
fi
if [ -n "${FORCE_DOMAIN:-}" ]; then
  set_or_append_env .env.prod "DOMAIN" "$FORCE_DOMAIN"
  set_or_append_env .env.prod "CORS_ORIGINS" "https://${FORCE_DOMAIN}"
fi

if ! grep -qE "^LETSENCRYPT_EMAIL=" .env.prod || grep -qE "^LETSENCRYPT_EMAIL=admin@yourdomain\.com" .env.prod; then
  set_or_append_env .env.prod "LETSENCRYPT_EMAIL" "$LETSENCRYPT_EMAIL"
fi
if [ -n "${FORCE_EMAIL:-}" ]; then
  set_or_append_env .env.prod "LETSENCRYPT_EMAIL" "$FORCE_EMAIL"
fi

ACTIVE_DOMAIN="$(grep -E '^DOMAIN=' .env.prod | head -n1 | cut -d= -f2- || echo "$DOMAIN")"
if grep -qE "^CORS_ORIGINS=https://dl\.yourdomain\.com" .env.prod; then
  set_or_append_env .env.prod "CORS_ORIGINS" "https://${ACTIVE_DOMAIN}"
fi

# Migrate legacy NGINX_HTTP_PORT=80 to 8088 so bundled Nginx binds 127.0.0.1:8088
# and never conflicts with the VPS host Nginx on port 80/443.
if grep -qE "^NGINX_HTTP_PORT=80$" .env.prod; then
  set_or_append_env .env.prod "NGINX_HTTP_PORT" "8088"
  echo "Updated NGINX_HTTP_PORT=8088 in .env.prod (avoids host port 80 conflict)"
fi

# Migrate legacy YOUTUBE_PLAYER_CLIENTS ordering in .env.prod
if grep -qE "^YOUTUBE_PLAYER_CLIENTS=(default,web_safari,tv,mweb,android_vr|default,mweb,android_vr,web_safari,ios,web_embedded,tv)$" .env.prod; then
  set_or_append_env .env.prod "YOUTUBE_PLAYER_CLIENTS" "android_vr,mweb,tv_simply,web_safari,ios,web_embedded,default"
  echo "Updated YOUTUBE_PLAYER_CLIENTS ordering in .env.prod"
fi

# Auto-generate strong HMAC_SECRET if placeholder is still present
if grep -q "REPLACE_WITH_OPENSSL_RAND_HEX_32" .env.prod; then
  if command -v openssl >/dev/null 2>&1; then
    SECRET="$(openssl rand -hex 32)"
  else
    SECRET="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  set_or_append_env .env.prod "HMAC_SECRET" "$SECRET"
  echo "Generated random 32-byte HMAC_SECRET in .env.prod"
fi

# Auto-generate strong GRAFANA_ADMIN_PASSWORD if default placeholder is still present
if grep -q "^GRAFANA_ADMIN_PASSWORD=change_me_in_prod" .env.prod; then
  if command -v openssl >/dev/null 2>&1; then
    GF_PASS="$(openssl rand -hex 12)"
  else
    GF_PASS="$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  set_or_append_env .env.prod "GRAFANA_ADMIN_PASSWORD" "$GF_PASS"
  echo "Generated random GRAFANA_ADMIN_PASSWORD in .env.prod"
fi

mkdir -p secrets/cookies
chmod 755 secrets secrets/cookies

if [ ! -f secrets/cookies/README.txt ]; then
  cat > secrets/cookies/README.txt <<'EOF'
Place optional Netscape-format cookie files here (NEVER commit them to git):
  youtube.txt
  x.txt
  instagram.txt
  facebook.txt

Use a dedicated throwaway account only. Files hot-reload automatically without restart.
EOF
fi

echo "Setup complete (Domain: ${ACTIVE_DOMAIN})."
