#!/usr/bin/env bash
# Stop and remove the SkyFleet Ops container. The database/ directory is preserved. Idempotent.
set -euo pipefail

CONTAINER_NAME="skyfleet-ops"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  docker rm -f "$CONTAINER_NAME" >/dev/null
  echo "Stopped and removed $CONTAINER_NAME."
else
  echo "$CONTAINER_NAME is not running."
fi
