#!/usr/bin/env bash
# Capture docs/assets/dashboard.png from the local docker compose stack.
#
# Usage:
#   ./scripts/capture-dashboard.sh [output-path]
#
# Requirements: docker (compose v2), Node.js/npx, curl, python3.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="${1:-docs/assets/dashboard.png}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8003}"
PLAYWRIGHT_VERSION="${PLAYWRIGHT_VERSION:-1.47.2}"

command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
command -v npx >/dev/null || { echo "npx (Node.js) is required" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }

echo "==> Starting stack"
docker compose up -d

echo "==> Waiting for dashboard at $DASHBOARD_URL"
for _ in $(seq 1 60); do
  if curl -fsS "$DASHBOARD_URL/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if ! curl -fsS "$DASHBOARD_URL/health" >/dev/null 2>&1; then
  echo "dashboard did not become healthy; check 'docker compose logs dashboard'" >&2
  exit 1
fi

echo "==> Seeding demo data"
python3 scripts/seed.py || echo "seed failed (continuing with current data)"

mkdir -p "$(dirname "$OUT")"

echo "==> Installing Chromium for Playwright (one time)"
npx --yes "playwright@$PLAYWRIGHT_VERSION" install chromium

echo "==> Capturing $OUT"
npx --yes "playwright@$PLAYWRIGHT_VERSION" screenshot \
  --viewport-size="1440,900" \
  --wait-for-timeout=3000 \
  "$DASHBOARD_URL" "$OUT"

echo "Saved $OUT"
