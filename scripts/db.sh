#!/usr/bin/env bash
# db.sh — Database operations for Smart AI Tutor
# Usage: ./scripts/db.sh <command> [options]

set -euo pipefail
source "$(dirname "$0")/_helpers.sh"

# Defaults — read from .env or docker-compose environment
DB_SERVICE="postgres"
DB_NAME="${POSTGRES_DB:-smart_tutor}"
DB_USER="${POSTGRES_USER:-postgres}"
BACKUP_DIR="${REPO_ROOT}/backups"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [options]

Database operations for the Smart AI Tutor PostgreSQL instance.

Commands:
  shell                   Open a psql shell inside the postgres container
  status                  Show database status and table counts
  backup [filename]       Dump the database to backups/ directory
  restore <filename>      Restore from a backup file (requires --force)
  reset                   Drop and recreate all tables (requires --force)
  tables                  List all tables with row counts
  query "SQL"             Run a single SQL query

Options:
  --force                 Required for destructive operations (restore, reset)
  -h, --help              Show this help

Examples:
  $(basename "$0") shell                   # open psql prompt
  $(basename "$0") status                  # show DB status
  $(basename "$0") tables                  # list tables with row counts
  $(basename "$0") backup                  # backup to backups/YYYY-MM-DD_HHMMSS.sql
  $(basename "$0") backup my_dump.sql      # backup to backups/my_dump.sql
  $(basename "$0") restore my_dump.sql --force   # restore from backup
  $(basename "$0") reset --force           # drop & recreate tables
  $(basename "$0") query "SELECT count(*) FROM users"
EOF
  exit 0
}

# ── Parse args ───────────────────────────────────────────────────────
COMMAND=""
FORCE=false
EXTRA=""

# Handle --help before any dependency checks
if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
  usage
fi

COMMAND="$1"; shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)  usage ;;
    --force)    FORCE=true; shift ;;
    *)          EXTRA="$1"; shift ;;
  esac
done

require_docker
require_compose_file

# Ensure postgres is running
if ! is_running "$DB_SERVICE"; then
  die "Postgres container is not running. Start it with: ./scripts/dev.sh postgres"
fi

# Helper: run psql in container
psql_exec() {
  dc exec -T "$DB_SERVICE" psql -U "$DB_USER" -d "$DB_NAME" "$@"
}

# ── Commands ─────────────────────────────────────────────────────────
case "$COMMAND" in
  shell)
    header "PostgreSQL Shell"
    info "Connecting to $DB_NAME as $DB_USER..."
    info "Type \\q to exit"
    echo ""
    dc exec "$DB_SERVICE" psql -U "$DB_USER" -d "$DB_NAME"
    ;;

  status)
    header "Database Status"
    echo ""
    info "Database: $DB_NAME"
    info "User: $DB_USER"
    echo ""

    echo -e "${BOLD}Connection Info:${NC}"
    psql_exec -c "SELECT current_database(), current_user, version();" 2>/dev/null || warn "Could not query database"

    echo ""
    echo -e "${BOLD}Database Size:${NC}"
    psql_exec -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME')) AS size;" 2>/dev/null || true

    echo ""
    echo -e "${BOLD}Active Connections:${NC}"
    psql_exec -c "SELECT count(*) AS active_connections FROM pg_stat_activity WHERE datname = '$DB_NAME';" 2>/dev/null || true
    ;;

  tables)
    header "Tables & Row Counts"
    psql_exec -c "
      SELECT schemaname, tablename,
             n_live_tup AS estimated_rows
      FROM pg_stat_user_tables
      ORDER BY n_live_tup DESC;
    " 2>/dev/null || die "Failed to query tables"
    ;;

  backup)
    header "Database Backup"
    mkdir -p "$BACKUP_DIR"

    local_file="${EXTRA:-$(date '+%Y-%m-%d_%H%M%S').sql}"
    backup_path="$BACKUP_DIR/$local_file"

    info "Backing up $DB_NAME to $backup_path..."
    dc exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists > "$backup_path"

    local size
    size=$(wc -c < "$backup_path" | tr -d ' ')
    ok "Backup complete: $backup_path ($(numfmt --to=iec "$size" 2>/dev/null || echo "$size bytes"))"
    ;;

  restore)
    if [[ -z "$EXTRA" ]]; then
      die "Usage: $(basename "$0") restore <filename> --force"
    fi

    local_file="$EXTRA"
    # Check in backups/ dir if not an absolute path
    if [[ ! "$local_file" = /* ]]; then
      local_file="$BACKUP_DIR/$local_file"
    fi

    if [[ ! -f "$local_file" ]]; then
      die "Backup file not found: $local_file"
    fi

    if ! $FORCE; then
      die "Restore is destructive. Pass --force to confirm."
    fi

    header "Database Restore"
    warn "This will overwrite data in $DB_NAME!"

    info "Restoring from $local_file..."
    dc exec -T "$DB_SERVICE" psql -U "$DB_USER" -d "$DB_NAME" < "$local_file"
    ok "Restore complete."
    ;;

  reset)
    if ! $FORCE; then
      die "Reset is destructive — it drops all tables. Pass --force to confirm."
    fi

    header "Database Reset"
    warn "Dropping all tables in $DB_NAME..."

    # Drop all tables in public schema
    psql_exec -c "
      DO \$\$ DECLARE
        r RECORD;
      BEGIN
        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
          EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
        END LOOP;
      END \$\$;
    "
    ok "All tables dropped."

    # Re-run init SQL if available
    local init_sql="$REPO_ROOT/docker/init-db.sql"
    if [[ -f "$init_sql" ]]; then
      info "Re-running init-db.sql..."
      dc exec -T "$DB_SERVICE" psql -U "$DB_USER" -d "$DB_NAME" < "$init_sql"
      ok "Schema recreated from init-db.sql"
    else
      warn "No init-db.sql found at $init_sql — database is empty."
    fi
    ;;

  query)
    if [[ -z "$EXTRA" ]]; then
      die "Usage: $(basename "$0") query \"SELECT ...\""
    fi
    psql_exec -c "$EXTRA"
    ;;

  -h|--help)
    usage
    ;;

  *)
    die "Unknown command: $COMMAND. Use --help for usage."
    ;;
esac
