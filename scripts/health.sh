#!/usr/bin/env bash
# health.sh — Service health dashboard for Smart AI Tutor
# Usage: ./scripts/health.sh [options]

set -euo pipefail
source "$(dirname "$0")/_helpers.sh"

WATCH=false
WATCH_INTERVAL=5

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Display a health dashboard for all Docker services.

Options:
  --watch       Refresh every ${WATCH_INTERVAL}s (Ctrl-C to stop)
  -h, --help    Show this help

Health checks:
  backend     HTTP GET http://localhost:8010/health
  frontend    HTTP GET http://localhost:4000
  postgres    pg_isready via docker exec
  redis       redis-cli ping via docker exec
  neo4j       HTTP GET http://localhost:7474
  other       Docker container status

EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)  usage ;;
    --watch)    WATCH=true; shift ;;
    -*)         die "Unknown option: $1" ;;
    *)          die "Unexpected argument: $1" ;;
  esac
done

require_docker
require_compose_file

# ── Health check for a single service ────────────────────────────────
check_service() {
  local svc="$1"
  local status="down"
  local detail=""

  # First check if container exists and is running
  if ! is_running "$svc"; then
    echo -e "  ${RED}●${NC} ${BOLD}$svc${NC} ${DIM}— not running${NC}"
    return
  fi

  case "$svc" in
    backend)
      if curl -sf --max-time 3 http://localhost:8010/health &>/dev/null; then
        status="healthy"
        detail="HTTP 200 on :8010/health"
      else
        status="unhealthy"
        detail="health endpoint not responding"
      fi
      ;;
    frontend)
      if curl -sf --max-time 3 http://localhost:4000 &>/dev/null; then
        status="healthy"
        detail="HTTP 200 on :4000"
      else
        status="unhealthy"
        detail="not responding on :4000"
      fi
      ;;
    postgres)
      if dc exec -T postgres pg_isready -U postgres &>/dev/null; then
        status="healthy"
        detail="accepting connections on :5432"
      else
        status="unhealthy"
        detail="pg_isready failed"
      fi
      ;;
    redis)
      if dc exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        status="healthy"
        detail="PONG on :6379"
      else
        status="unhealthy"
        detail="ping failed"
      fi
      ;;
    neo4j)
      if curl -sf --max-time 3 http://localhost:7474 &>/dev/null; then
        status="healthy"
        detail="browser UI on :7474"
      else
        status="unhealthy"
        detail="not responding on :7474"
      fi
      ;;
    dynamodb-local)
      if curl -sf --max-time 3 http://localhost:8000 &>/dev/null; then
        status="healthy"
        detail="HTTP on :8000"
      else
        # DynamoDB local returns 400 on GET / but that still means it's up
        if curl -s --max-time 3 -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null | grep -qE "^[2-4]"; then
          status="healthy"
          detail="responding on :8000"
        else
          status="unhealthy"
          detail="not responding on :8000"
        fi
      fi
      ;;
    prometheus)
      if curl -sf --max-time 3 http://localhost:9090/-/healthy &>/dev/null; then
        status="healthy"
        detail="healthy on :9090"
      else
        status="unhealthy"
        detail="not responding"
      fi
      ;;
    grafana)
      if curl -sf --max-time 3 http://localhost:3001/api/health &>/dev/null; then
        status="healthy"
        detail="API healthy on :3001"
      else
        status="unhealthy"
        detail="not responding"
      fi
      ;;
    *)
      # Generic: just running = ok
      status="running"
      detail="container up"
      ;;
  esac

  case "$status" in
    healthy)   echo -e "  ${GREEN}●${NC} ${BOLD}$svc${NC} ${DIM}— $detail${NC}" ;;
    running)   echo -e "  ${GREEN}●${NC} ${BOLD}$svc${NC} ${DIM}— $detail${NC}" ;;
    unhealthy) echo -e "  ${YELLOW}●${NC} ${BOLD}$svc${NC} ${DIM}— $detail${NC}" ;;
    *)         echo -e "  ${RED}●${NC} ${BOLD}$svc${NC} ${DIM}— $detail${NC}" ;;
  esac
}

# ── Dashboard render ─────────────────────────────────────────────────
render() {
  local timestamp
  timestamp=$(date '+%Y-%m-%d %H:%M:%S')

  echo -e "${BOLD}Smart AI Tutor — Health Dashboard${NC}  ${DIM}$timestamp${NC}"
  echo ""

  echo -e "${BOLD}Core Services${NC}"
  for svc in "${CORE_SERVICES[@]}"; do
    check_service "$svc"
  done

  echo ""
  echo -e "${BOLD}Monitoring Stack${NC}"
  for svc in "${MONITORING_SERVICES[@]}"; do
    check_service "$svc"
  done

  echo ""
  local total running
  total=$(dc ps --services 2>/dev/null | wc -l | tr -d ' ')
  running=$(running_services | wc -l | tr -d ' ')
  echo -e "${DIM}Containers: $running/$total running${NC}"
}

# ── Main ─────────────────────────────────────────────────────────────
if $WATCH; then
  while true; do
    clear
    render
    echo ""
    echo -e "${DIM}Refreshing every ${WATCH_INTERVAL}s — Ctrl-C to stop${NC}"
    sleep "$WATCH_INTERVAL"
  done
else
  render
fi
