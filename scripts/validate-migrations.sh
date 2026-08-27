#!/usr/bin/env bash

set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-migration_validation}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_SSL_MODE="${POSTGRES_SSL_MODE:-disable}"

export SECRETS_PROVIDER="${SECRETS_PROVIDER:-env}"
export POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_SSL_MODE

db_url="$(python3 - <<'PY'
import os
from urllib.parse import quote

print(
    "postgresql+psycopg2://"
    f"{quote(os.environ['POSTGRES_USER'], safe='')}:"
    f"{quote(os.environ['POSTGRES_PASSWORD'], safe='')}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
    f"/{quote(os.environ['POSTGRES_DB'], safe='')}"
    f"?sslmode={quote(os.environ['POSTGRES_SSL_MODE'], safe='')}"
)
PY
)"

# Never log db_url here; it contains credentials.
echo "Validating Alembic migrations against ${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
ALEMBIC_DB_URL="${db_url}" python3 -m alembic -c alembic.ini upgrade head
ALEMBIC_DB_URL="${db_url}" python3 -m alembic -c alembic.ini current
