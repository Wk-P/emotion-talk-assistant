#!/usr/bin/env bash
# One-shot health check across local dev, the remote Docker container,
# the Cloudflare Tunnel, and the public URLs.
# Usage: ./scripts/status.sh

set -uo pipefail
SSH_HOST="Lab-tailscale[public-linux]"

echo "===== local dev ====="
lsof -iTCP -sTCP:LISTEN -P 2>/dev/null | grep -E ":8000|:5173|:5174" || echo "(nothing listening)"

echo
echo "===== remote: docker container ====="
ssh -o ConnectTimeout=8 "$SSH_HOST" "docker compose -f ~/emotion-talk/docker-compose.yml ps" 2>&1

echo
echo "===== remote: cloudflared service ====="
ssh -o ConnectTimeout=8 "$SSH_HOST" "systemctl is-active cloudflared" 2>&1

echo
echo "===== remote: backend local health ====="
ssh -o ConnectTimeout=8 "$SSH_HOST" "curl -s http://localhost:8000/api/health" 2>&1
echo

echo
echo "===== public: backend API ====="
curl -s -m 10 https://emotion-api.knettf.com/api/health
echo

echo
echo "===== public: frontend ====="
curl -s -m 10 -o /dev/null -w "HTTP %{http_code}\n" https://emotion.knettf.com
