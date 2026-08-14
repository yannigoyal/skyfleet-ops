#!/usr/bin/env bash
# Poll an HTTP endpoint until it answers, or give up at the deadline.
# Usage: wait_for_health.sh <url> [timeout_seconds]
# Exit: 0 ready | 1 deadline passed with no answer | 2 curl unavailable
#
# No `set -e`: a failing curl is the expected steady state of this loop while a
# container boots, not an error.
set -uo pipefail

URL="${1:-}"
TIMEOUT="${2:-60}"

if [[ -z "$URL" ]]; then
  echo "usage: wait_for_health.sh <url> [timeout_seconds]" >&2
  exit 64
fi

if ! command -v curl >/dev/null 2>&1; then
  exit 2
fi

DEADLINE=$(( $(date +%s) + TIMEOUT ))

while [[ $(date +%s) -lt $DEADLINE ]]; do
  # -o /dev/null and no -v: never echo response bodies or headers, since the
  # caller polls a container started with --env-file .env. Errors are silenced
  # too: a refused connection is the expected state while the container boots,
  # and printing one per retry would bury the script's own status lines.
  if curl -fs --max-time 2 -o /dev/null "$URL" 2>/dev/null; then
    exit 0
  fi
  sleep 0.25
done

exit 1
