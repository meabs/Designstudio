#!/usr/bin/env bash
# Runs the direct-editing browser test against a disposable studio (fixture runners, fresh storage, free port).
# Skips with a clear message (exit 0) when Playwright or Chrome is not available; set E2E_REQUIRED=1 to make that an error.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
skip() { echo "e2e: skipped, $1"; [ "${E2E_REQUIRED:-0}" = 1 ] && exit 1; exit 0; }
command -v node >/dev/null || skip "node not found"
CHROME="${CHROME_PATH:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)}"
[ -n "$CHROME" ] || skip "Chrome not found (set CHROME_PATH)"
NM=""
for d in "$ROOT/node_modules" "$ROOT/tests/node_modules" "$ROOT/promo/node_modules" "$ROOT/apps/ui/node_modules"; do
  [ -d "$d/@playwright/test" ] && NM="$d" && break
done
[ -n "$NM" ] || skip "Playwright not installed (npm install --no-save @playwright/test)"
WORK="$(mktemp -d)"; STORE="$(mktemp -d)"
PORT="$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')"
ln -s "$NM" "$WORK/node_modules"; cp "$ROOT/tests/edit.mjs" "$WORK/edit.mjs"
STUDIO_SEED_FIXTURES=1 STUDIO_STORAGE="$STORE" PORT="$PORT" python3 "$ROOT/apps/api/server.py" >"$WORK/server.log" 2>&1 &
SERVER=$!
cleanup() { kill "$SERVER" 2>/dev/null; wait "$SERVER" 2>/dev/null; rm -rf "$WORK" "$STORE"; }
trap cleanup EXIT
for _ in $(seq 1 50); do curl -fs "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1 && break; sleep 0.2; done
curl -fs "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1 || { echo "e2e: server did not start"; cat "$WORK/server.log"; exit 1; }
(cd "$WORK" && STUDIO_URL="http://127.0.0.1:$PORT" CHROME_PATH="$CHROME" node edit.mjs)
