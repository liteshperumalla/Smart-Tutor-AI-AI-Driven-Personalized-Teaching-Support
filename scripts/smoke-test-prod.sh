#!/bin/bash
# =============================================================================
# Production Smoke Test — Task 16
# Tests the live Oracle Cloud backend and (optionally) Vercel frontend.
#
# Usage:
#   VM_IP=<YOUR_ORACLE_IP> ./scripts/smoke-test-prod.sh
#   VM_IP=1.2.3.4 VERCEL_URL=https://smart-tutor-xyz.vercel.app ./scripts/smoke-test-prod.sh
# =============================================================================

set -euo pipefail

VM_IP="${VM_IP:?Set VM_IP to your Oracle Cloud public IP}"
VERCEL_URL="${VERCEL_URL:-}"
API="http://$VM_IP/api/v1"
PASS=0; FAIL=0

check() {
  local label="$1"; local expected="$2"; local actual="$3"
  if echo "$actual" | grep -q "$expected"; then
    echo "  [PASS] $label"
    PASS=$((PASS+1))
  else
    echo "  [FAIL] $label (expected '$expected' in response)"
    echo "         Got: $actual" | head -3
    FAIL=$((FAIL+1))
  fi
}

echo ""
echo "=== Smart AI Tutor — Production Smoke Tests ==="
echo "    API base: $API"
echo ""

echo "[1] Health check"
HEALTH=$(curl -sf "$API/health" 2>&1 || echo "CURL_ERROR")
check "GET /health → status" '"status"' "$HEALTH"

echo ""
echo "[2] Auth — invalid credentials rejected"
AUTH_FAIL=$(curl -sf -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"nobody","password":"wrong"}' \
  -o /dev/null -w "%{http_code}" 2>&1 || echo "000")
if [ "$AUTH_FAIL" = "401" ]; then
  echo "  [PASS] POST /auth/login with bad creds → 401"
  PASS=$((PASS+1))
else
  echo "  [FAIL] Expected 401, got $AUTH_FAIL"
  FAIL=$((FAIL+1))
fi

echo ""
echo "[3] Admin lockdown — no token → 401 or 403"
ADMIN_NO_AUTH=$(curl -sf "$API/admin/users" \
  -o /dev/null -w "%{http_code}" 2>&1 || echo "000")
if [ "$ADMIN_NO_AUTH" = "401" ] || [ "$ADMIN_NO_AUTH" = "403" ]; then
  echo "  [PASS] GET /admin/users without token → $ADMIN_NO_AUTH"
  PASS=$((PASS+1))
else
  echo "  [FAIL] Expected 401/403, got $ADMIN_NO_AUTH"
  FAIL=$((FAIL+1))
fi

echo ""
echo "[4] Detailed health check"
DETAILED=$(curl -sf "$API/health/detailed" 2>&1 || echo "CURL_ERROR")
check "GET /health/detailed → checks" '"checks"' "$DETAILED"

if [ -n "$VERCEL_URL" ]; then
  echo ""
  echo "[5] Vercel frontend reachable"
  FE=$(curl -sf -o /dev/null -w "%{http_code}" "$VERCEL_URL" 2>&1 || echo "000")
  if [ "$FE" = "200" ]; then
    echo "  [PASS] Vercel frontend → 200"
    PASS=$((PASS+1))
  else
    echo "  [FAIL] Vercel frontend → $FE (expected 200)"
    FAIL=$((FAIL+1))
  fi
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "All smoke tests PASSED." || exit 1
