#!/usr/bin/env bash

set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-migration_validation}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_SSL_MODE="${POSTGRES_SSL_MODE:-disable}"

export SECRETS_PROVIDER="${SECRETS_PROVIDER:-env}"

db_url="postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}?sslmode=${POSTGRES_SSL_MODE}"

echo "Validating Alembic migrations against ${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
ALEMBIC_DB_URL="${db_url}" python -m alembic -c alembic.ini upgrade head
ALEMBIC_DB_URL="${db_url}" python -m alembic -c alembic.ini current

