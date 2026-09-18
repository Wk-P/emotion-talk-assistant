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

echo "==> building image on server"
ssh "$SSH_HOST" "cd $REMOTE_DIR/backend && docker build -t $DOCKERHUB_IMAGE ."

echo "==> pushing to Docker Hub"
ssh "$SSH_HOST" "docker push $DOCKERHUB_IMAGE"

echo "==> restarting container"
ssh "$SSH_HOST" "cd $REMOTE_DIR && docker compose up -d"

echo "==> health check"
sleep 2
ssh "$SSH_HOST" "curl -s http://localhost:8000/api/health"
echo
echo "==> public health check"
curl -s https://emotion-api.knettf.com/api/health
echo
echo "done."
