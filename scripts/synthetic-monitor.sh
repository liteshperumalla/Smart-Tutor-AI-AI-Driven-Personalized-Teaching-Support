#!/usr/bin/env bash
# =============================================================================
# Synthetic Monitor — Always-On Production Health Probes
# Smart AI Tutor Platform
#
# Runs a series of real API transaction probes against the live production
# endpoints on a schedule. Failures generate Slack alerts and set exit code 1
# (which fails GitHub Actions and triggers PagerDuty via Alertmanager).
#
# Probed transactions:
#   1. Backend /ready     — liveness check
#   2. Backend /health    — full dependency health
#   3. Backend /metrics   — Prometheus scrape endpoint reachable
#   4. Frontend root (/)  — Next.js frontend serving
#   5. Auth flow          — POST /api/v1/auth/login with a synthetic account
#   6. Chat authorization — GET /api/v1/chat/sessions with a test token
#   7. RAG pipeline       — GET /api/v1/rag/health with an admin token
#
# Usage:
#   ./scripts/synthetic-monitor.sh
#
# Environment variables (set as GitHub Secrets or .env):
#   PRODUCTION_API_URL         — e.g. https://api.smart-ai-tutor.com
#   PRODUCTION_APP_URL         — e.g. https://smart-ai-tutor.vercel.app
#   SYNTHETIC_TEST_USERNAME    — test account username
#   SYNTHETIC_TEST_PASSWORD    — test account password
#   SYNTHETIC_ADMIN_TOKEN      — long-lived admin JWT for admin probes
#   ALERTMANAGER_SLACK_WEBHOOK_URL — Slack webhook for failure alerts
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Config ────────────────────────────────────────────────────────────────────
API_URL="${PRODUCTION_API_URL:-}"
API_URL="${API_URL%/}"
APP_URL="${PRODUCTION_APP_URL:-}"
APP_URL="${APP_URL%/}"
SLACK_WEBHOOK="${ALERTMANAGER_SLACK_WEBHOOK_URL:-}"
MAX_LATENCY_MS=5000        # Alert if any probe exceeds 5s
TIMEOUT_SEC=15             # curl timeout per probe
PROBE_LOG="/tmp/synthetic-monitor-$(date +%Y%m%d-%H%M%S).log"

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[PROBE]${NC}  $*" | tee -a "$PROBE_LOG"; }
ok()      { echo -e "${GREEN}[PASS]${NC}   $*" | tee -a "$PROBE_LOG"; }
fail()    { echo -e "${RED}[FAIL]${NC}   $*" | tee -a "$PROBE_LOG"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}   $*" | tee -a "$PROBE_LOG"; }

FAILED_PROBES=()
PROBE_COUNT=0
PASS_COUNT=0

# ── Probe Helper ─────────────────────────────────────────────────────────────
probe() {
  local name="$1"
  local method="$2"
  local url="$3"
  shift 3
  local extra_args=("$@")

  PROBE_COUNT=$((PROBE_COUNT + 1))
  info "[$PROBE_COUNT] ${name} → ${method} ${url}"

  local start_ms; start_ms=$(date +%s%3N)
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time "$TIMEOUT_SEC" \
    -X "$method" \
    "${extra_args[@]}" \
    "$url" 2>>"$PROBE_LOG") || {
    fail "[$PROBE_COUNT] ${name}: curl error (timeout or connection refused)"
    FAILED_PROBES+=("$name")
    return 1
  }
  local end_ms; end_ms=$(date +%s%3N)
  local latency_ms=$((end_ms - start_ms))

  if [[ "$http_code" -ge 200 && "$http_code" -lt 400 ]]; then
    ok "[$PROBE_COUNT] ${name}: HTTP ${http_code} (${latency_ms}ms)"
    PASS_COUNT=$((PASS_COUNT + 1))
    if [[ "$latency_ms" -gt "$MAX_LATENCY_MS" ]]; then
      warn "[$PROBE_COUNT] ${name}: Latency ${latency_ms}ms exceeds threshold ${MAX_LATENCY_MS}ms"
    fi
  else
    fail "[$PROBE_COUNT] ${name}: HTTP ${http_code} (${latency_ms}ms)"
    FAILED_PROBES+=("$name (HTTP ${http_code})")
  fi
}

# ── Slack Alert ──────────────────────────────────────────────────────────────
send_slack_alert() {
  local message="$1"
  if [[ -z "$SLACK_WEBHOOK" ]]; then
    warn "ALERTMANAGER_SLACK_WEBHOOK_URL not set — skipping Slack alert"
    return 0
  fi

  curl -s -o /dev/null -X POST "$SLACK_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"🚨 *Synthetic Monitor FAILED* — Smart AI Tutor Production\n${message}\"}" || true
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  if [[ -z "$API_URL" || -z "$APP_URL" ]]; then
    fail "PRODUCTION_API_URL and PRODUCTION_APP_URL must both be configured; refusing to probe fallback endpoints."
    exit 2
  fi

  for url in "$API_URL" "$APP_URL"; do
    if [[ ! "$url" =~ ^https:// ]]; then
      fail "Synthetic probe URL must use HTTPS: $url"
      exit 2
    fi
  done

  echo ""
  echo -e "${CYAN}=====================================================================${NC}"
  echo -e "${CYAN}   Smart AI Tutor — Synthetic Production Monitor                    ${NC}"
  echo -e "${CYAN}   $(date -u '+%Y-%m-%dT%H:%M:%SZ')                               ${NC}"
  echo -e "${CYAN}=====================================================================${NC}"
  echo ""

  # ── Transaction 1: Liveness ─────────────────────────────────────────────
  probe "Backend /ready" GET "${API_URL}/ready"

  # ── Transaction 2: Full Dependency Health ────────────────────────────────
  probe "Backend /health" GET "${API_URL}/health"

  # ── Transaction 3: Prometheus Metrics Scrape ─────────────────────────────
  probe "Backend /metrics" GET "${API_URL}/metrics"

  # ── Transaction 4: Frontend Root ─────────────────────────────────────────
  if [[ -n "$APP_URL" ]]; then
    probe "Frontend /" GET "${APP_URL}/"
  fi

  # ── Transaction 5: Auth — POST /api/v1/auth/login ───────────────────────
  SYNTHETIC_USERNAME="${SYNTHETIC_TEST_USERNAME:-}"
  SYNTHETIC_PASS="${SYNTHETIC_TEST_PASSWORD:-}"

  if [[ -n "$SYNTHETIC_USERNAME" && -n "$SYNTHETIC_PASS" ]]; then
    AUTH_BODY="{\"username\":\"${SYNTHETIC_USERNAME}\",\"password\":\"${SYNTHETIC_PASS}\"}"
    probe "Auth /api/v1/auth/login" POST "${API_URL}/api/v1/auth/login" \
      -H "Content-Type: application/json" \
      -d "$AUTH_BODY"
  elif [[ -n "$SYNTHETIC_USERNAME" || -n "$SYNTHETIC_PASS" ]]; then
    fail "Both SYNTHETIC_TEST_USERNAME and SYNTHETIC_TEST_PASSWORD are required for the auth probe"
  else
    warn "SYNTHETIC_TEST_USERNAME/PASSWORD not set — skipping auth probe"
  fi

  # ── Transaction 6: Authenticated Chat API ─────────────────────────────────
  ADMIN_TOKEN="${SYNTHETIC_ADMIN_TOKEN:-}"
  if [[ -n "$ADMIN_TOKEN" ]]; then
    probe "Chat /api/v1/chat/sessions" GET "${API_URL}/api/v1/chat/sessions" \
      -H "Authorization: Bearer ${ADMIN_TOKEN}"

    # ── Transaction 7: Admin RAG Health ──────────────────────────────────
    probe "Admin /api/v1/rag/health" GET "${API_URL}/api/v1/rag/health" \
      -H "Authorization: Bearer ${ADMIN_TOKEN}"
  else
    warn "SYNTHETIC_ADMIN_TOKEN not set — skipping chat and admin probes"
  fi

  # ── Summary ──────────────────────────────────────────────────────────────
  echo ""
  echo -e "${CYAN}=====================================================================${NC}"
  FAIL_COUNT="${#FAILED_PROBES[@]}"
  echo -e "   Results: ${GREEN}${PASS_COUNT} PASSED${NC} / ${RED}${FAIL_COUNT} FAILED${NC} / ${PROBE_COUNT} total probes"
  echo -e "${CYAN}=====================================================================${NC}"
  echo ""

  if [[ "$FAIL_COUNT" -gt 0 ]]; then
    fail "SYNTHETIC MONITOR ALERT — ${FAIL_COUNT} probe(s) failed:"
    for probe_name in "${FAILED_PROBES[@]}"; do
      fail "  • ${probe_name}"
    done

    ALERT_MSG="*Failed probes (${FAIL_COUNT}/${PROBE_COUNT}):*\n"
    for probe_name in "${FAILED_PROBES[@]}"; do
      ALERT_MSG="${ALERT_MSG}  • ${probe_name}\n"
    done
    ALERT_MSG="${ALERT_MSG}\n*Environment:* \`${API_URL}\`"
    ALERT_MSG="${ALERT_MSG}\n*Time:* $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

    send_slack_alert "$ALERT_MSG"
    exit 1
  else
    ok "All ${PASS_COUNT}/${PROBE_COUNT} synthetic probes passed ✅"
    exit 0
  fi
}

main "$@"
