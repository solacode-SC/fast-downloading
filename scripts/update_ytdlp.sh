#!/usr/bin/env bash
set -euo pipefail

# Runs runtime yt-dlp update with self-test & rollback inside active backend containers.
STACK="${1:-auto}"

run_update() {
  local project="$1"
  local compose_file="$2"
  local env_file="$3"
  echo "Updating yt-dlp in project '${project}'..."
  docker compose -p "$project" -f "$compose_file" --env-file "$env_file" exec -T api python3 -m app.services.updater
  docker compose -p "$project" -f "$compose_file" --env-file "$env_file" restart api worker
  echo "Updated and restarted api + worker in '${project}'."
}

if [ "$STACK" = "prod" ] || docker ps --format '{{.Names}}' | grep -q '^vdl-prod-api'; then
  run_update "vdl-prod" "docker-compose.prod.yml" ".env.prod"
elif [ "$STACK" = "dev" ] || docker ps --format '{{.Names}}' | grep -q '^vdl-dev-api'; then
  run_update "vdl-dev" "docker-compose.dev.yml" ".env.dev"
else
  echo "No running vdl-prod or vdl-dev api container found."
  exit 1
fi
