#!/usr/bin/env bash
# logs.sh — Smart log viewer for Smart AI Tutor services
# Usage: ./scripts/logs.sh [options] [service ...]

set -euo pipefail
source "$(dirname "$0")/_helpers.sh"

FOLLOW=false
TAIL_LINES=100
SINCE=""
GREP_PATTERN=""
SERVICES=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [options] [service ...]

View and filter Docker Compose service logs.

Options:
  -f, --follow          Follow log output in real-time
  -n, --lines NUM       Number of recent lines to show (default: $TAIL_LINES)
  --since DURATION      Show logs since duration (e.g., 5m, 1h, 2h30m)
  --grep PATTERN        Filter log lines matching PATTERN
  --errors              Show only ERROR/CRITICAL/Exception lines
  -h, --help            Show this help

Services:
  No args → backend + frontend logs
  Use service names: backend, frontend, postgres, redis, neo4j, etc.
  Special: --all for all services

Examples:
  $(basename "$0") -f                        # follow backend+frontend
  $(basename "$0") -f backend --grep "ERROR"  # follow backend errors
  $(basename "$0") --since 30m postgres       # postgres logs from last 30m
  $(basename "$0") --errors --all             # errors across all services
EOF
  exit 0
}

# ── Parse args ───────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)    usage ;;
    -f|--follow)  FOLLOW=true; shift ;;
    -n|--lines)   TAIL_LINES="$2"; shift 2 ;;
    --since)      SINCE="$2"; shift 2 ;;
    --grep)       GREP_PATTERN="$2"; shift 2 ;;
    --errors)     GREP_PATTERN="ERROR|CRITICAL|Exception|Traceback|FATAL"; shift ;;
    --all)        SERVICES=("${ALL_SERVICES[@]}"); shift ;;
    -*)           die "Unknown option: $1. Use --help for usage." ;;
    *)            SERVICES+=("$1"); shift ;;
  esac
done

# Default services
if [[ ${#SERVICES[@]} -eq 0 ]]; then
  SERVICES=(backend frontend)
fi

require_docker
require_compose_file

# ── Build docker compose logs command ────────────────────────────────
CMD=(dc logs)

CMD+=(--tail "$TAIL_LINES")

if $FOLLOW; then
  CMD+=(-f)
fi

if [[ -n "$SINCE" ]]; then
  CMD+=(--since "$SINCE")
fi

# Timestamps for easier debugging
CMD+=(-t)

CMD+=("${SERVICES[@]}")

# ── Execute ──────────────────────────────────────────────────────────
if [[ -n "$GREP_PATTERN" ]]; then
  info "Filtering logs for: $GREP_PATTERN"
  info "Services: ${SERVICES[*]}"
  echo ""
  # Use grep --line-buffered for streaming with -f
  "${CMD[@]}" 2>&1 | grep --line-buffered -iE "$GREP_PATTERN" || true
else
  info "Services: ${SERVICES[*]}"
  echo ""
  "${CMD[@]}"
fi
