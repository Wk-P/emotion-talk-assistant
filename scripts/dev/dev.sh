#!/usr/bin/env bash
# Control local dev servers (backend uvicorn + frontend vite).
# Usage: ./scripts/dev/dev.sh {start|stop|restart|status}

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/require-branch.sh" dev
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PID_DIR="$ROOT_DIR/.dev-pids"
mkdir -p "$PID_DIR"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

# Local test accounts, created (or reset to these passwords) on every start.
# Local database only — never use these on the server.
TEST_ADMIN_USER="${TEST_ADMIN_USER:-testadmin}"
TEST_ADMIN_PASSWORD="${TEST_ADMIN_PASSWORD:-testadmin123}"
TEST_USER_USER="${TEST_USER_USER:-testuser}"
TEST_USER_PASSWORD="${TEST_USER_PASSWORD:-testuser123}"
BACKEND_URL="http://localhost:8000"

start() {
  (cd "$BACKEND_DIR" && uv run python -m app.db.dev_users \
    "$TEST_ADMIN_USER" "$TEST_ADMIN_PASSWORD" "$TEST_USER_USER" "$TEST_USER_PASSWORD") \
    || echo "(could not create the test accounts — see the error above)"

  if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
    echo "backend already running (pid $(cat "$BACKEND_PID_FILE"))"
  else
    (cd "$BACKEND_DIR" && nohup uv run uvicorn app.main:app --port 8000 --reload > "$PID_DIR/backend.log" 2>&1 &)
    sleep 1
    pgrep -f "uvicorn app.main:app --port 8000" | head -1 > "$BACKEND_PID_FILE"
    echo "backend started (pid $(cat "$BACKEND_PID_FILE")), log: $PID_DIR/backend.log"
  fi

  if [ -f "$FRONTEND_PID_FILE" ] && kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
    echo "frontend already running (pid $(cat "$FRONTEND_PID_FILE"))"
  else
    (cd "$FRONTEND_DIR" && nohup npm run dev > "$PID_DIR/frontend.log" 2>&1 &)
    sleep 1
    pgrep -f "vite" | head -1 > "$FRONTEND_PID_FILE"
    echo "frontend started (pid $(cat "$FRONTEND_PID_FILE")), log: $PID_DIR/frontend.log"
  fi

  print_access
}

# Vite moves to the next free port when 5173 is taken, so read it from the log.
frontend_url() {
  local url=""
  for _ in $(seq 1 15); do
    url="$(sed 's/\x1b\[[0-9;]*m//g' "$PID_DIR/frontend.log" 2>/dev/null | grep -Eo 'http://localhost:[0-9]+/?' | head -1 || true)"
    [ -n "$url" ] && break
    sleep 1
  done
  echo "${url:-http://localhost:5173/}"
}

print_access() {
  local url
  url="$(frontend_url)"
  echo ""
  echo "=============================================="
  echo " 用户端:     $url"
  echo " 管理后台:   ${url%/}/admin"
  echo " 后端接口:   $BACKEND_URL/docs"
  echo "----------------------------------------------"
  echo " 测试管理员: $TEST_ADMIN_USER / $TEST_ADMIN_PASSWORD"
  echo " 测试用户:   $TEST_USER_USER / $TEST_USER_PASSWORD"
  echo "=============================================="
}

stop() {
  for name in backend frontend; do
    pid_file="$PID_DIR/$name.pid"
    if [ -f "$pid_file" ]; then
      pid="$(cat "$pid_file")"
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" && echo "$name stopped (pid $pid)"
      else
        echo "$name not running"
      fi
      rm -f "$pid_file"
    else
      echo "$name has no pid file (not started via this script?)"
    fi
  done
}

status() {
  print_access
  echo "--- listening ports ---"
  lsof -iTCP -sTCP:LISTEN -P 2>/dev/null | grep -E ":8000|:5173|:5174" || echo "(none found)"
  echo "--- tracked pids ---"
  for name in backend frontend; do
    pid_file="$PID_DIR/$name.pid"
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      echo "$name: running (pid $(cat "$pid_file"))"
    else
      echo "$name: not running"
    fi
  done
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
