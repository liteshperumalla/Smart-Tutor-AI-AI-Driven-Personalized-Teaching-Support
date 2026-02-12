#!/usr/bin/env bash
# test.sh — Unified test runner for Smart AI Tutor
# Usage: ./scripts/test.sh [options]

set -euo pipefail
source "$(dirname "$0")/_helpers.sh"

TARGET="all"
VERBOSE=false
MARKER=""
EXTRA_ARGS=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [options] [-- pytest_args...]

Run tests for backend, frontend, or both.

Options:
  --backend         Run backend tests only (pytest)
  --frontend        Run frontend tests only (lint + typecheck + build)
  --lint            Run frontend linting only
  --typecheck       Run frontend type checking only
  -m, --marker M    Run only pytest tests with marker M (unit, integration, slow, auth, api, database)
  -v, --verbose     Verbose output
  -h, --help        Show this help

Extra arguments after -- are passed directly to pytest.

Examples:
  $(basename "$0")                     # run all tests
  $(basename "$0") --backend           # backend only
  $(basename "$0") --backend -m unit   # backend unit tests only
  $(basename "$0") --frontend          # lint + typecheck + build
  $(basename "$0") --lint              # linting only
  $(basename "$0") --backend -- -k "test_health"  # specific test
EOF
  exit 0
}

# ── Parse args ───────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)      usage ;;
    --backend)      TARGET="backend"; shift ;;
    --frontend)     TARGET="frontend"; shift ;;
    --lint)         TARGET="lint"; shift ;;
    --typecheck)    TARGET="typecheck"; shift ;;
    -m|--marker)    MARKER="$2"; shift 2 ;;
    -v|--verbose)   VERBOSE=true; shift ;;
    --)             shift; EXTRA_ARGS=("$@"); break ;;
    -*)             die "Unknown option: $1. Use --help for usage." ;;
    *)              die "Unexpected argument: $1" ;;
  esac
done

require_docker
require_compose_file

FAILURES=0

# ── Backend tests ────────────────────────────────────────────────────
run_backend_tests() {
  header "Backend Tests (pytest)"

  if ! is_running backend; then
    warn "Backend container is not running. Starting it..."
    dc up -d backend
    sleep 3
  fi

  local pytest_cmd="pytest tests/ -v --tb=short"

  if [[ -n "$MARKER" ]]; then
    pytest_cmd+=" -m $MARKER"
    info "Marker filter: $MARKER"
  fi

  if $VERBOSE; then
    pytest_cmd+=" -s"
  fi

  if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    pytest_cmd+=" ${EXTRA_ARGS[*]}"
  fi

  info "Running: $pytest_cmd"
  echo ""

  if dc exec -T backend bash -c "$pytest_cmd"; then
    ok "Backend tests passed"
  else
    err "Backend tests failed"
    FAILURES=$((FAILURES + 1))
  fi
}

# ── Frontend lint ────────────────────────────────────────────────────
run_frontend_lint() {
  header "Frontend Lint"

  if ! is_running frontend; then
    warn "Frontend container is not running. Starting it..."
    dc up -d frontend
    sleep 3
  fi

  info "Running: npm run lint"
  if dc exec -T frontend npm run lint; then
    ok "Lint passed"
  else
    err "Lint failed"
    FAILURES=$((FAILURES + 1))
  fi
}

# ── Frontend typecheck ───────────────────────────────────────────────
run_frontend_typecheck() {
  header "Frontend Type Check"

  if ! is_running frontend; then
    warn "Frontend container is not running. Starting it..."
    dc up -d frontend
    sleep 3
  fi

  info "Running: npx tsc --noEmit"
  if dc exec -T frontend npx tsc --noEmit; then
    ok "Type check passed"
  else
    err "Type check failed"
    FAILURES=$((FAILURES + 1))
  fi
}

# ── Frontend build check ────────────────────────────────────────────
run_frontend_build() {
  header "Frontend Build Check"

  if ! is_running frontend; then
    warn "Frontend container is not running. Starting it..."
    dc up -d frontend
    sleep 3
  fi

  info "Running: npm run build"
  if dc exec -T frontend npm run build; then
    ok "Build succeeded"
  else
    err "Build failed"
    FAILURES=$((FAILURES + 1))
  fi
}

# ── Execute ──────────────────────────────────────────────────────────
case "$TARGET" in
  all)
    run_backend_tests
    run_frontend_lint
    run_frontend_typecheck
    ;;
  backend)
    run_backend_tests
    ;;
  frontend)
    run_frontend_lint
    run_frontend_typecheck
    run_frontend_build
    ;;
  lint)
    run_frontend_lint
    ;;
  typecheck)
    run_frontend_typecheck
    ;;
esac

# ── Summary ──────────────────────────────────────────────────────────
echo ""
if [[ $FAILURES -eq 0 ]]; then
  ok "All checks passed."
  exit 0
else
  err "$FAILURES check(s) failed."
  exit 1
fi
