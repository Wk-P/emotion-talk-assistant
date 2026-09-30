#!/usr/bin/env bash
# Build the frontend and deploy it to the `emotion-talk-frontend` Cloudflare
# Worker (static assets, custom domain emotion.knettf.com). It's a Worker,
# not a Pages project — `wrangler pages deploy` would try to create a new,
# unrelated Pages project. The Worker name comes from frontend/wrangler.jsonc.
# Usage: ./scripts/deploy-frontend.sh

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/frontend"

echo "==> building"
npm run build

echo "==> deploying Worker"
npx wrangler deploy

echo "done. live at https://emotion.knettf.com"
