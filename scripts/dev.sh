#!/usr/bin/env bash
# dev.sh — Rebuild and restart Smart AI Tutor services
# Usage: ./scripts/dev.sh [options] [service ...]
#   No args  → rebuild & restart backend + frontend
#   service  → rebuild & restart only named services

set -euo pipefail
source "$(dirname "$0")/_helpers.sh"

# ── Defaults ─────────────────────────────────────────────────────────
PULL=false
CLEAN=false
SERVICES=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [options] [service ...]

Rebuild and restart Docker Compose services.

Options:
  --all         Rebuild all services (core + monitoring)
  --pull        Pull latest base images before building
  --clean       Remove orphan containers and dangling images after build
  -h, --help    Show this help

Examples:
  $(basename "$0")                  # rebuild backend + frontend (default)
  $(basename "$0") backend          # rebuild backend only
  $(basename "$0") --all            # rebuild everything
  $(basename "$0") --pull frontend  # pull base images, then rebuild frontend
EOF
  exit 0
}

# ── Parse args ───────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)  usage ;;
    --all)      SERVICES=("${ALL_SERVICES[@]}"); shift ;;
    --pull)     PULL=true; shift ;;
    --clean)    CLEAN=true; shift ;;
    -*)         die "Unknown option: $1. Use --help for usage." ;;
    *)          SERVICES+=("$1"); shift ;;
  esac
done

# Default to backend + frontend
if [[ ${#SERVICES[@]} -eq 0 ]]; then
  SERVICES=(backend frontend)
fi

# ── Preflight ────────────────────────────────────────────────────────
require_docker
require_compose_file

header "Rebuilding: ${SERVICES[*]}"

# ── Optional pull ────────────────────────────────────────────────────
if $PULL; then
  info "Pulling latest base images..."
  dc pull "${SERVICES[@]}" || warn "Some images could not be pulled (continuing)"
fi

# ── Build & restart ──────────────────────────────────────────────────
info "Building images..."
dc build --parallel "${SERVICES[@]}"

info "Restarting services..."
dc up -d --no-deps --build "${SERVICES[@]}"

# ── Optional cleanup ─────────────────────────────────────────────────
if $CLEAN; then
  info "Removing orphan containers..."
  dc up -d --remove-orphans
  info "Pruning dangling images..."
  docker image prune -f --filter "label=com.docker.compose.project" 2>/dev/null || true
fi

# ── Status ───────────────────────────────────────────────────────────
echo ""
info "Waiting for services to start..."
sleep 3

for svc in "${SERVICES[@]}"; do
  if is_running "$svc"; then
    ok "$svc is running"
  else
    warn "$svc is not running yet"
  fi
done

echo ""
ok "Done. Use ./scripts/health.sh for detailed health status."
