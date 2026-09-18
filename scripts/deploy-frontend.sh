#!/usr/bin/env bash
# Build the frontend and deploy it to Cloudflare Pages.
# Usage: ./scripts/deploy-frontend.sh

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="emotion-talk-frontend"

cd "$ROOT_DIR/frontend"

echo "==> building"
npm run build

echo "==> deploying to Cloudflare Pages ($PROJECT_NAME)"
npx wrangler pages deploy dist --project-name="$PROJECT_NAME"

echo "done. live at https://emotion.knettf.com"
