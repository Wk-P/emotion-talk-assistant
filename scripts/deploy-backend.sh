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

# The server's .env is never rsynced (it holds server-only settings), but the
# OpenAI settings must match the local, known-good ones — a stale key there
# once made every AI reply fail in production. Only these lines are touched;
# the server .env is backed up first (5 most recent kept) when anything
# changes. The key travels over ssh stdin and is never printed.
echo "==> syncing OpenAI settings from backend/.env"
SYNC_LINES="$(grep -E '^(OPENAI_API_KEY|OPENAI_MODEL)=' "$ROOT_DIR/backend/.env" 2>/dev/null || true)"
if [ -z "$SYNC_LINES" ]; then
  echo "    no OPENAI_* lines in backend/.env — leaving the server's as they are" >&2
else
  REMOTE_SYNC='
set -e
changed=0
while IFS= read -r line; do
  key=${line%%=*}
  grep -qxF "$line" .env && continue
  [ $changed -eq 0 ] && cp -p .env ".env.bak-$(date +%Y%m%d-%H%M%S)"
  changed=1
  awk -v k="$key" -v nl="$line" "BEGIN{d=0} index(\$0, k\"=\")==1{print nl; d=1; next} {print} END{if(!d) print nl}" .env > .env.new
  cat .env.new > .env && rm .env.new
  echo "    updated $key"
done
[ $changed -eq 0 ] && echo "    already up to date"
ls -1t .env.bak-* 2>/dev/null | tail -n +6 | xargs -r rm --
'
  printf '%s\n' "$SYNC_LINES" | ssh "$SSH_HOST" "cd $REMOTE_DIR && bash -c $(printf %q "$REMOTE_SYNC")"
fi

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

# /api/health only proves the server is up. Send one real JSON-mode request
# with the model actually in use (the one chosen on the admin page, else
# OPENAI_MODEL), so a bad key or model fails the deploy here instead of
# surfacing as a broken chat for users.
echo "==> AI key check"
if ! ssh "$SSH_HOST" "cd $REMOTE_DIR && docker compose exec -T backend python -" <<'PY'
import asyncio
from app.db.session import async_session_maker
from app.services.model_settings import current_model, probe

async def main():
    async with async_session_maker() as db:
        model = await current_model(db)
    ok, err = await probe(model)
    if not ok:
        raise SystemExit(f"    model {model} not usable: {err}")
    print(f"    OpenAI key OK, model {model} answers")

asyncio.run(main())
PY
then
  echo "AI check failed: the server's OPENAI_API_KEY or the chosen model is wrong (see the error above)" >&2
  exit 1
fi

# The crisis/support resources live in the database, filled from
# backend/app/db/seed.py. Re-run it on every deploy so edits to that file go
# live; it upserts by id, so existing rows are updated, never duplicated.
echo "==> syncing crisis resources from seed.py"
if ! ssh "$SSH_HOST" "cd $REMOTE_DIR && docker compose exec -T backend python -m app.db.seed"; then
  echo "seeding crisis resources failed (see the error above)" >&2
  exit 1
fi

echo "==> public health check"
curl -s https://emotion-api.knettf.com/api/health
echo
echo "done."
