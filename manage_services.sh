#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
FASTAPI_PID_FILE="$LOG_DIR/backend_api.pid"
FASTAPI_LOG_FILE="$LOG_DIR/backend_api.log"
NEXT_PID_FILE="$LOG_DIR/next_dev.pid"
NEXT_LOG_FILE="$LOG_DIR/next_dev.log"
OLLAMA_PID_FILE="$LOG_DIR/ollama.pid"
OLLAMA_LOG_FILE="$LOG_DIR/ollama.log"
VENV_BIN="$ROOT_DIR/venv/bin"
FASTAPI_PORT="${FASTAPI_PORT:-8010}"
NEXT_DEV_PORT="${NEXT_DEV_PORT:-4000}"

mkdir -p "$LOG_DIR"

is_running() {
  local pid="$1"
  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

start_fastapi() {
  if [ ! -x "$VENV_BIN/uvicorn" ]; then
    echo "FastAPI: missing uvicorn executable at $VENV_BIN/uvicorn"
    exit 1
  fi

  if [ -f "$FASTAPI_PID_FILE" ]; then
    local pid
    pid="$(cat "$FASTAPI_PID_FILE")"
    if is_running "$pid"; then
      echo "FastAPI already running (pid ${pid})"
      return
    fi
    rm -f "$FASTAPI_PID_FILE"
  fi

  echo "Starting FastAPI on port ${FASTAPI_PORT}..."
  nohup "$VENV_BIN/uvicorn" backend.api.main:app --host 0.0.0.0 --port "$FASTAPI_PORT" \
    > "$FASTAPI_LOG_FILE" 2>&1 &
  echo $! > "$FASTAPI_PID_FILE"
  echo "FastAPI started (pid $(cat "$FASTAPI_PID_FILE")). Logs: $FASTAPI_LOG_FILE"
}

start_next() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "React UI: npm is not available in PATH"
    exit 1
  fi

  if [ -f "$NEXT_PID_FILE" ]; then
    local pid
    pid="$(cat "$NEXT_PID_FILE")"
    if is_running "$pid"; then
      echo "React UI already running (pid ${pid})"
      return
    fi
    rm -f "$NEXT_PID_FILE"
  fi

  echo "Starting React UI on port ${NEXT_DEV_PORT}..."
  (
    cd "$ROOT_DIR/frontend"
    nohup npm run dev -- --port "$NEXT_DEV_PORT" > "$NEXT_LOG_FILE" 2>&1 &
    echo $! > "$NEXT_PID_FILE"
  )
  echo "React UI started (pid $(cat "$NEXT_PID_FILE")). Logs: $NEXT_LOG_FILE"
}

start_ollama() {
  if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama: ollama command not found in PATH"
    exit 1
  fi

  if [ -f "$OLLAMA_PID_FILE" ]; then
    local pid
    pid="$(cat "$OLLAMA_PID_FILE")"
    if is_running "$pid"; then
      echo "Ollama already running (pid ${pid})"
      return
    fi
    rm -f "$OLLAMA_PID_FILE"
  fi

  echo "Starting Ollama on port 11434..."
  nohup ollama serve > "$OLLAMA_LOG_FILE" 2>&1 &
  echo $! > "$OLLAMA_PID_FILE"
  echo "Ollama started (pid $(cat "$OLLAMA_PID_FILE")). Logs: $OLLAMA_LOG_FILE"
}

stop_process() {
  local name="$1"
  local pid_file="$2"
  if [ ! -f "$pid_file" ]; then
    echo "$name: not running (no pid file)"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if is_running "$pid"; then
    echo "Stopping $name (pid ${pid})..."
    kill "$pid"
    wait "$pid" 2>/dev/null || true
  else
    echo "$name: pid ${pid} is not active, cleaning up stale pid file"
  fi

  rm -f "$pid_file"
  echo "$name stopped."
}

status_process() {
  local name="$1"
  local pid_file="$2"
  if [ ! -f "$pid_file" ]; then
    echo "$name: not running"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if is_running "$pid"; then
    echo "$name: running (pid ${pid})"
  else
    echo "$name: pid file exists but process not running"
  fi
}

start_all() {
  start_ollama
  start_fastapi
  start_next
}

stop_all() {
  stop_process "FastAPI" "$FASTAPI_PID_FILE"
  stop_process "React UI" "$NEXT_PID_FILE"
  stop_process "Ollama" "$OLLAMA_PID_FILE"
}

status_all() {
  status_process "FastAPI" "$FASTAPI_PID_FILE"
  status_process "React UI" "$NEXT_PID_FILE"
  status_process "Ollama" "$OLLAMA_PID_FILE"
}

case "${1:-start}" in
  start)
    if [ -n "${2:-}" ]; then
      case "$2" in
        backend|fastapi) start_fastapi ;;
        frontend|next) start_next ;;
        ollama) start_ollama ;;
        *) echo "Unknown service: $2"; exit 1 ;;
      esac
    else
      start_all
    fi
    ;;
  stop)
    if [ -n "${2:-}" ]; then
      case "$2" in
        backend|fastapi) stop_process "FastAPI" "$FASTAPI_PID_FILE" ;;
        frontend|next) stop_process "React UI" "$NEXT_PID_FILE" ;;
        ollama) stop_process "Ollama" "$OLLAMA_PID_FILE" ;;
        *) echo "Unknown service: $2"; exit 1 ;;
      esac
    else
      stop_all
    fi
    ;;
  restart)
    if [ -n "${2:-}" ]; then
      case "$2" in
        backend|fastapi)
          stop_process "FastAPI" "$FASTAPI_PID_FILE"
          start_fastapi
          ;;
        frontend|next)
          stop_process "React UI" "$NEXT_PID_FILE"
          start_next
          ;;
        ollama)
          stop_process "Ollama" "$OLLAMA_PID_FILE"
          start_ollama
          ;;
        *) echo "Unknown service: $2"; exit 1 ;;
      esac
    else
      stop_all
      start_all
    fi
    ;;
  status)
    status_all
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status} [backend|frontend|ollama]"
    exit 1
    ;;
esac
