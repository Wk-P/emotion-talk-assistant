#!/usr/bin/env bash
# Control local dev servers (backend uvicorn + frontend vite).
# Usage: ./scripts/dev.sh {start|stop|restart|status}

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PID_DIR="$ROOT_DIR/.dev-pids"
mkdir -p "$PID_DIR"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

start() {
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
