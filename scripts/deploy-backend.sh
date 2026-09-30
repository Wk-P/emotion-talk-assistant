#!/usr/bin/env bash
# Sync backend code to the Linux server, rebuild the Docker image there
# (matches its x86_64 arch), push to Docker Hub, and restart the container.
# Usage: ./scripts/deploy-backend.sh

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSH_HOST="Lab-tailscale[public-linux]"
DOCKERHUB_IMAGE="soar009/emotion-talk-backend:latest"
REMOTE_DIR="~/emotion-talk"

echo "==> syncing backend/ to $SSH_HOST:$REMOTE_DIR/backend/"
rsync -av --delete \
  --exclude='.venv' --exclude='.git' --exclude='data' --exclude='.env' \
  --exclude='__pycache__' --exclude='*.pyc' \
  "$ROOT_DIR/backend/" "$SSH_HOST:$REMOTE_DIR/backend/"

# The backend migrates/cleans the DB on startup (app/db/session.py), so keep
# a copy from before each deploy. Keeps the 10 most recent.
echo "==> backing up database"
# \$HOME, not ~: the path sits inside quotes on the remote side, where ~
# is not expanded (sqlite3 then looks for a literal "~" directory).
ssh "$SSH_HOST" "mkdir -p \$HOME/emotion-talk-backups \
  && sqlite3 $REMOTE_DIR/data/app.db \".backup \$HOME/emotion-talk-backups/app-\$(date +%Y%m%d-%H%M%S).db\" \
  && ls -1t \$HOME/emotion-talk-backups/app-*.db | tail -n +11 | xargs -r rm --"

echo "==> building image on server"
ssh "$SSH_HOST" "cd $REMOTE_DIR/backend && docker build -t $DOCKERHUB_IMAGE ."

echo "==> pushing to Docker Hub"
ssh "$SSH_HOST" "docker push $DOCKERHUB_IMAGE"

echo "==> restarting container"
ssh "$SSH_HOST" "cd $REMOTE_DIR && docker compose up -d"
# Each build leaves the previous image untagged; drop those.
ssh "$SSH_HOST" "docker image prune -f >/dev/null"

# The container needs a few seconds to start — a single early curl gets
# connection-refused and, under `set -e`, aborted the script after an
# otherwise successful deploy.
echo "==> health check"
if ! ssh "$SSH_HOST" "for i in \$(seq 15); do curl -sf http://localhost:8000/api/health && exit 0; sleep 2; done; exit 1"; then
  echo "backend did not become healthy within 30s — check: ssh $SSH_HOST 'cd $REMOTE_DIR && docker compose logs --tail 50 backend'" >&2
  exit 1
fi
echo
echo "==> public health check"
curl -s https://emotion-api.knettf.com/api/health
echo
echo "done."
