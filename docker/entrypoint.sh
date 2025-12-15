#!/usr/bin/env bash
set -e

APP_HOME="/app"
cd "$APP_HOME"

: "${STREAMLIT_SERVER_PORT:=8501}"
: "${STREAMLIT_SERVER_ADDRESS:=0.0.0.0}"
: "${FASTAPI_PORT:=8000}"
: "${APP_MODE:=streamlit}"

if [ "$APP_MODE" = "fastapi" ]; then
  exec uvicorn backend.api.main:app --host 0.0.0.0 --port "${PORT:-$FASTAPI_PORT}"
else
  exec streamlit run app.py \
    --server.port="${PORT:-$STREAMLIT_SERVER_PORT}" \
    --server.address="${STREAMLIT_SERVER_ADDRESS}"
fi
