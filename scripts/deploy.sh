#!/usr/bin/env bash
# Deploy backend and frontend together.
#
#   ./scripts/deploy.sh             both (backend first, then frontend)
#   ./scripts/deploy.sh --backend   backend only
#   ./scripts/deploy.sh --frontend  frontend only
#
# Checks everything locally first, so a broken build stops the run before
# anything goes live — never half-deployed. Backend goes out before the
# frontend because a new frontend may call new API routes, while a new
# backend still serves the old frontend fine in between.
# The actual work is done by deploy-backend.sh / deploy-frontend.sh.

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DO_BACKEND=1
DO_FRONTEND=1
case "${1:-}" in
  "") ;;
  --backend) DO_FRONTEND=0 ;;
  --frontend) DO_BACKEND=0 ;;
  -h | --help)
    sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *)
    echo "unknown option: $1 (use --backend, --frontend or nothing)" >&2
    exit 1
    ;;
esac

START=$SECONDS
step_start=$SECONDS
SUMMARY=()
finish_step() {
  SUMMARY+=("$1 ($((SECONDS - step_start))s)")
  step_start=$SECONDS
}

echo "######## 1/3 checks ########"
if [ "$DO_FRONTEND" = 1 ]; then
  echo "==> frontend: type-check + build"
  (cd "$ROOT_DIR/frontend" && npm run build)
fi
if [ "$DO_BACKEND" = 1 ]; then
  echo "==> backend: app loads"
  (cd "$ROOT_DIR/backend" && uv run python -c "import app.main" && echo "    ok")
fi
finish_step "checks"

if [ "$DO_BACKEND" = 1 ]; then
  echo
  echo "######## 2/3 backend ########"
  bash "$ROOT_DIR/scripts/deploy-backend.sh"
  finish_step "backend"
fi

if [ "$DO_FRONTEND" = 1 ]; then
  echo
  echo "######## 3/3 frontend ########"
  bash "$ROOT_DIR/scripts/deploy-frontend.sh"
  finish_step "frontend"
fi

echo
echo "######## all done in $((SECONDS - START))s ########"
for line in "${SUMMARY[@]}"; do echo "  ✓ $line"; done
[ "$DO_BACKEND" = 1 ] && echo "  API:  https://emotion-api.knettf.com"
[ "$DO_FRONTEND" = 1 ] && echo "  site: https://emotion.knettf.com"
exit 0
