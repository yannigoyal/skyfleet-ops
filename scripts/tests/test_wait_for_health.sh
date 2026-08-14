#!/usr/bin/env bash
# Behavioral test for scripts/wait_for_health.sh. Needs no Docker: it serves a
# temp docroot containing an api/health file with python3's stdlib http.server
# and polls it with the real helper.
set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WAIT="$SCRIPTS_DIR/wait_for_health.sh"
FAILURES=0

free_port() {
  python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

DOCROOT="$(mktemp -d)"
mkdir -p "$DOCROOT/api"
printf 'ok' > "$DOCROOT/api/health"
trap 'rm -rf "$DOCROOT"' EXIT

# Case 1: endpoint already answering when the poll starts -> exit 0.
PORT="$(free_port)"
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DOCROOT" >/dev/null 2>&1 &
SERVER_PID=$!
sleep 0.6
if ! "$WAIT" "http://127.0.0.1:$PORT/api/health" 10; then
  echo "FAIL case 1: endpoint was already answering but the poll did not report ready"
  FAILURES=$((FAILURES + 1))
fi
kill "$SERVER_PID" 2>/dev/null
wait "$SERVER_PID" 2>/dev/null

# Case 2: endpoint starts answering ~2s late -> exit 0, and only after it is up.
PORT="$(free_port)"
( sleep 2; python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DOCROOT" >/dev/null 2>&1 ) &
LATE_PID=$!
START="$(date +%s)"
if ! "$WAIT" "http://127.0.0.1:$PORT/api/health" 20; then
  echo "FAIL case 2: endpoint came up late and the poll never detected it"
  FAILURES=$((FAILURES + 1))
fi
LATE_ELAPSED=$(( $(date +%s) - START ))
if [ "$LATE_ELAPSED" -lt 2 ]; then
  echo "FAIL case 2: reported ready after ${LATE_ELAPSED}s, before the endpoint existed"
  FAILURES=$((FAILURES + 1))
fi
pkill -f "http.server $PORT" 2>/dev/null
kill "$LATE_PID" 2>/dev/null
wait "$LATE_PID" 2>/dev/null

# Case 3: nothing listening -> non-zero, and bounded rather than hanging.
PORT="$(free_port)"
START="$(date +%s)"
if "$WAIT" "http://127.0.0.1:$PORT/api/health" 3; then
  echo "FAIL case 3: nothing was listening but the poll reported ready"
  FAILURES=$((FAILURES + 1))
fi
DEAD_ELAPSED=$(( $(date +%s) - START ))
if [ "$DEAD_ELAPSED" -ge 15 ]; then
  echo "FAIL case 3: poll ran ${DEAD_ELAPSED}s against a dead port instead of honoring its deadline"
  FAILURES=$((FAILURES + 1))
fi

if [ "$FAILURES" -eq 0 ]; then
  echo "wait_for_health: 3/3 cases passed (late start detected after ${LATE_ELAPSED}s, dead port gave up after ${DEAD_ELAPSED}s)"
fi
exit "$FAILURES"
