#!/usr/bin/env bash
# _helpers.sh — Shared helper functions for Smart AI Tutor scripts
# Source this file; do not execute directly.

set -euo pipefail

# ── Repo root (one level up from scripts/) ──────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.yml"

# ── Colors ───────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  CYAN='\033[0;36m'
  BOLD='\033[1m'
  DIM='\033[2m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' CYAN='' BOLD='' DIM='' NC=''
fi

# ── Output helpers ───────────────────────────────────────────────────
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()     { echo -e "${RED}[ERR]${NC}   $*" >&2; }
die()     { err "$@"; exit 1; }
header()  { echo -e "\n${BOLD}── $* ──${NC}"; }

# ── Dependency checks ────────────────────────────────────────────────
require_cmd() {
  local cmd="$1"
  local hint="${2:-}"
  if ! command -v "$cmd" &>/dev/null; then
    if [[ -n "$hint" ]]; then
      die "'$cmd' is required but not found. $hint"
    else
      die "'$cmd' is required but not found."
    fi
  fi
}

require_docker() {
  require_cmd docker "Install Docker: https://docs.docker.com/get-docker/"
  if ! docker info &>/dev/null; then
    die "Docker daemon is not running. Start Docker Desktop and try again."
  fi
  require_cmd "docker" "docker compose plugin required"
  if ! docker compose version &>/dev/null; then
    die "docker compose plugin not found. Update Docker Desktop."
  fi
}

require_compose_file() {
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    die "docker-compose.yml not found at $COMPOSE_FILE"
  fi
}

# ── Docker shortcuts ─────────────────────────────────────────────────
dc() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

# List running service names
running_services() {
  dc ps --services --filter "status=running" 2>/dev/null
}

# Check if a specific service is running
is_running() {
  local svc="$1"
  dc ps --services --filter "status=running" 2>/dev/null | grep -qx "$svc"
}

# ── Wait for a service to become healthy ─────────────────────────────
# Usage: wait_for_healthy <service> [timeout_seconds]
wait_for_healthy() {
  local svc="$1"
  local timeout="${2:-60}"
  local elapsed=0
  local interval=2

  while (( elapsed < timeout )); do
    local health
    health=$(docker inspect --format='{{.State.Health.Status}}' "$(dc ps -q "$svc" 2>/dev/null)" 2>/dev/null || echo "missing")
    case "$health" in
      healthy)  return 0 ;;
      missing)  ;; # container not up yet
    esac
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  return 1
}

# ── HTTP readiness probe ─────────────────────────────────────────────
# Usage: wait_for_http <url> [timeout_seconds]
wait_for_http() {
  local url="$1"
  local timeout="${2:-60}"
  local elapsed=0
  local interval=2

  while (( elapsed < timeout )); do
    if curl -sf --max-time 3 "$url" &>/dev/null; then
      return 0
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  return 1
}

# ── Confirmation prompt ──────────────────────────────────────────────
confirm() {
  local msg="${1:-Continue?}"
  echo -en "${YELLOW}$msg [y/N]: ${NC}"
  read -r ans
  [[ "$ans" =~ ^[Yy]$ ]]
}

# ── All known services (core + monitoring) ───────────────────────────
CORE_SERVICES=(backend frontend postgres redis neo4j dynamodb-local ollama)
MONITORING_SERVICES=(prometheus grafana node-exporter postgres-exporter redis-exporter)
ALL_SERVICES=("${CORE_SERVICES[@]}" "${MONITORING_SERVICES[@]}")
