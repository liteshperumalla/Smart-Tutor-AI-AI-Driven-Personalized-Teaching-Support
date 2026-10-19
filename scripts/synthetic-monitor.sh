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
# Environment variables (set as GitHub Secrets, vars, or .env):
#   PRODUCTION_API_URL         — e.g. https://api.smart-ai-tutor.com or http://52.2.3.101:8010
#   PRODUCTION_APP_URL         — e.g. https://smart-ai-tutor.vercel.app
#   SYNTHETIC_TEST_USERNAME    — test account username
#   SYNTHETIC_TEST_PASSWORD    — test account password
#   SYNTHETIC_ADMIN_TOKEN      — long-lived admin JWT for admin probes
#   ALERTMANAGER_SLACK_WEBHOOK_URL — Slack webhook for failure alerts
#   SLACK_WEBHOOK_URL_SMART_TUTOR_AI — Fallback Slack webhook
#   SYNTHETIC_INSECURE_SKIP_VERIFY — set 'true' to allow self-signed certs (-k)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── URL Normalization Helper ──────────────────────────────────────────────────
normalize_url() {
  local raw="$1"
  local cleaned
  # Strip \r, leading/trailing whitespace, and quotes
  cleaned=$(printf '%s' "$raw" | tr -d '\r' | sed -e 's/^[[:space:]"'"'"']*//' -e 's/[[:space:]"'"'"']*$//')
  # Strip trailing slashes
  cleaned="${cleaned%/}"
  # If non-empty and missing scheme, infer based on hostname
  if [[ -n "$cleaned" && ! "$cleaned" =~ ^https?:// ]]; then
    if [[ "$cleaned" =~ ^([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+|localhost|127\.0\.0\.1)(:|/|#|\?|$) ]]; then
      cleaned="http://${cleaned}"
    else
      cleaned="https://${cleaned}"
    fi
  fi
  printf '%s' "$cleaned"
}

# ── Config ────────────────────────────────────────────────────────────────────
API_URL=$(normalize_url "${PRODUCTION_API_URL:-}")
APP_URL=$(normalize_url "${PRODUCTION_APP_URL:-}")
SLACK_WEBHOOK="${ALERTMANAGER_SLACK_WEBHOOK_URL:-${SLACK_WEBHOOK_URL_SMART_TUTOR_AI:-${SLACK_WEBHOOK_URL_APP_DEV_ANALYTICS:-}}}"
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

get_time_ms() {
  local now
  now=$(date +%s%3N 2>/dev/null || true)
  if [[ "$now" =~ ^[0-9]+$ ]]; then
    printf '%s' "$now"
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import time; print(int(time.time() * 1000))'
  else
    printf '%s' "$(( $(date +%s) * 1000 ))"
  fi
}

# ── Probe Helper ─────────────────────────────────────────────────────────────
probe() {
  local name="$1"
  local method="$2"
  local url="$3"
  shift 3
  local extra_args=()
  if [ "$#" -gt 0 ]; then
    extra_args=("$@")
  fi

  PROBE_COUNT=$((PROBE_COUNT + 1))
  info "[$PROBE_COUNT] ${name} → ${method} ${url}"

  local start_ms
  start_ms=$(get_time_ms)
  local http_code
  local curl_flags=(-s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT_SEC" -L)
  if [[ "${SYNTHETIC_INSECURE_SKIP_VERIFY:-false}" == "true" ]]; then
    curl_flags+=(-k)
  fi

  if [ "${#extra_args[@]}" -gt 0 ]; then
    curl_flags+=("${extra_args[@]}")
  fi

  http_code=$(curl "${curl_flags[@]}" \
    -X "$method" \
    "$url" 2>>"$PROBE_LOG") || {
    fail "[$PROBE_COUNT] ${name}: curl error (timeout or connection refused)"
    FAILED_PROBES+=("$name")
    return 1
  }

  local end_ms
  end_ms=$(get_time_ms)
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
    warn "Slack webhook not configured — skipping Slack alert"
    return 0
  fi

  curl -s -o /dev/null -X POST "$SLACK_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"🚨 *Synthetic Monitor FAILED* — Smart AI Tutor Production\n${message}\"}" || true
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  if [[ -z "$API_URL" && -z "$APP_URL" ]]; then
    fail "Neither PRODUCTION_API_URL nor PRODUCTION_APP_URL is configured; refusing to probe without target."
    exit 2
  fi

  local targets=()
  [[ -n "$API_URL" ]] && targets+=("$API_URL")
  [[ -n "$APP_URL" ]] && targets+=("$APP_URL")

  for url in "${targets[@]}"; do
    if [[ ! "$url" =~ ^https?:// ]]; then
      fail "Synthetic probe URL must be a valid HTTP or HTTPS URL: $url"
      exit 2
    fi
    if [[ "$url" =~ ^http:// ]]; then
      warn "Probe target uses HTTP (unencrypted): $url"
    fi
  done

  echo ""
  echo -e "${CYAN}=====================================================================${NC}"
  echo -e "${CYAN}   Smart AI Tutor — Synthetic Production Monitor                    ${NC}"
  echo -e "${CYAN}   $(date -u '+%Y-%m-%dT%H:%M:%SZ')                               ${NC}"
  echo -e "${CYAN}=====================================================================${NC}"
  echo ""

  # ── Backend Probes ────────────────────────────────────────────────────────
  if [[ -n "$API_URL" ]]; then
    # ── Transaction 1: Liveness ─────────────────────────────────────────────
    probe "Backend /ready" GET "${API_URL}/ready"

    # ── Transaction 2: Full Dependency Health ────────────────────────────────
    probe "Backend /health" GET "${API_URL}/health"

    # ── Transaction 3: Prometheus Metrics Scrape ─────────────────────────────
    probe "Backend /metrics" GET "${API_URL}/metrics"

    # ── Transaction 5: Auth — POST /api/v1/auth/login ───────────────────────
    SYNTHETIC_USERNAME="${SYNTHETIC_TEST_USERNAME:-}"
    SYNTHETIC_PASS="${SYNTHETIC_TEST_PASSWORD:-}"

    if [[ -n "$SYNTHETIC_USERNAME" && -n "$SYNTHETIC_PASS" ]]; then
      if command -v jq >/dev/null 2>&1; then
        AUTH_BODY=$(jq -nc --arg u "$SYNTHETIC_USERNAME" --arg p "$SYNTHETIC_PASS" '{"username": $u, "password": $p}')
      elif command -v python3 >/dev/null 2>&1; then
        AUTH_BODY=$(python3 -c 'import json, sys; print(json.dumps({"username": sys.argv[1], "password": sys.argv[2]}))' "$SYNTHETIC_USERNAME" "$SYNTHETIC_PASS")
      else
        local esc_u esc_p
        esc_u="${SYNTHETIC_USERNAME//\\/\\\\}"
        esc_u="${esc_u//\"/\\\"}"
        esc_p="${SYNTHETIC_PASS//\\/\\\\}"
        esc_p="${esc_p//\"/\\\"}"
        AUTH_BODY="{\"username\":\"${esc_u}\",\"password\":\"${esc_p}\"}"
      fi
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
  else
    warn "PRODUCTION_API_URL not set — skipping backend API probes"
  fi

  # ── Frontend Probe ────────────────────────────────────────────────────────
  if [[ -n "$APP_URL" ]]; then
    # ── Transaction 4: Frontend Root ─────────────────────────────────────────
    probe "Frontend /" GET "${APP_URL}/"
  else
    warn "PRODUCTION_APP_URL not set — skipping frontend root probe"
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
    ALERT_MSG="${ALERT_MSG}\n*Environment:* \`${API_URL:-none} / ${APP_URL:-none}\`"
    ALERT_MSG="${ALERT_MSG}\n*Time:* $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

    send_slack_alert "$ALERT_MSG"
    exit 1
  else
    ok "All ${PASS_COUNT}/${PROBE_COUNT} synthetic probes passed ✅"
    exit 0
  fi
}

main "$@"
