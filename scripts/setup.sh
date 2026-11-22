#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env.dev ]; then
  cp .env.dev.example .env.dev
  echo "Created .env.dev from .env.dev.example"
else
  echo ".env.dev already exists (kept)"
fi

if [ ! -f .env.prod ]; then
  cp .env.prod.example .env.prod
  if command -v openssl >/dev/null 2>&1; then
    SECRET="$(openssl rand -hex 32)"
    sed -i.bak "s/REPLACE_WITH_OPENSSL_RAND_HEX_32/${SECRET}/" .env.prod && rm -f .env.prod.bak
    echo "Created .env.prod with generated HMAC_SECRET"
  else
    echo "Created .env.prod (remember to replace HMAC_SECRET!)"
  fi
else
  echo ".env.prod already exists (kept)"
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

echo "Setup complete."
