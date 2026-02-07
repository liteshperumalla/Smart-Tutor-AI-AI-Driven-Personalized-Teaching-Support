#!/usr/bin/env bash
set -e

APP_HOME="/app"
cd "$APP_HOME"

: "${FASTAPI_PORT:=8000}"
exec uvicorn backend.api.main:app --host 0.0.0.0 --port "${PORT:-$FASTAPI_PORT}"
