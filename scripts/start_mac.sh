#!/usr/bin/env bash
# Build (if needed) and run the SkyFleet Ops container. Idempotent.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_NAME="skyfleet-ops"
CONTAINER_NAME="skyfleet-ops"
PORT="8000"

if [[ ! -f .env ]]; then
  echo "No .env file found. Copy .env.example to .env and set OPENROUTER_API_KEY first."
  exit 1
fi

BUILD=false
for arg in "$@"; do
  [[ "$arg" == "--build" ]] && BUILD=true
done

if $BUILD || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Building $IMAGE_NAME..."
  docker build -f docker/Dockerfile -t "$IMAGE_NAME" .
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "Removing existing container..."
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

echo "Starting $CONTAINER_NAME on port $PORT..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -v skyfleet-data:/app/database \
  -p "${PORT}:8000" \
  --env-file .env \
  "$IMAGE_NAME"

echo "SkyFleet Ops is running at http://localhost:${PORT}"

if command -v open >/dev/null 2>&1; then
  open "http://localhost:${PORT}"
fi
