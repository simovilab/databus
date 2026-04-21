#!/bin/sh
set -e

if [ ! -f /app/package.json ]; then
  echo "package.json not found in /app. Did you mount the frontend folder?"
  exit 1
fi

if [ ! -f /app/node_modules/.modules.yaml ]; then
  pnpm install
fi

exec pnpm run dev --host 0.0.0.0 --port "${NUXT_PORT:-3000}"
