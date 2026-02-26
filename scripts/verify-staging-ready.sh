#!/bin/bash
# Verify that staging slot(s) are ready for QA: backend, Airflow, and frontend must all respond.
#
# Usage:
#   ./scripts/verify-staging-ready.sh <slot_id> [slot_id ...]
#
# Examples:
#   ./scripts/verify-staging-ready.sh 1
#   ./scripts/verify-staging-ready.sh 1 2 3
#
# Exit: 0 only if all required services for all specified slots are healthy, 1 otherwise.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SLOTS=("$@")
BASE_URL="${STAGING_BASE_URL:-https://justapply.net}"

if [[ ${#SLOTS[@]} -eq 0 ]]; then
  echo "Usage: $0 <slot_id> [slot_id ...]"
  echo "  slot_id: 1-10"
  echo "Checks for each slot: backend /api/health, Airflow /airflow/health, frontend /"
  exit 1
fi

OVERALL_FAIL=0

for SLOT in "${SLOTS[@]}"; do
  if [[ ! "$SLOT" =~ ^[1-9]$|^10$ ]]; then
    echo -e "${RED}Invalid slot: $SLOT (must be 1-10)${NC}"
    OVERALL_FAIL=1
    continue
  fi

  if [[ "$BASE_URL" == "https://justapply.net" ]]; then
    API_BASE="https://staging-${SLOT}.justapply.net"
  else
    API_BASE="${BASE_URL%/}/staging-${SLOT}"
  fi

  BACKEND_HEALTH="${API_BASE}/api/health"
  AIRFLOW_HEALTH="${API_BASE}/airflow/health"
  FRONTEND_URL="${API_BASE}/"

  echo "--- Verifying staging slot $SLOT ---"
  echo "  Backend:  $BACKEND_HEALTH"
  echo "  Airflow:  $AIRFLOW_HEALTH"
  echo "  Frontend: $FRONTEND_URL"

  SLOT_FAIL=0

  # Required: backend health 200
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$BACKEND_HEALTH" 2>/dev/null || echo "000")
  if [[ "$HTTP" == "200" ]]; then
    echo -e "  ${GREEN}✓ Backend OK (200)${NC}"
  else
    echo -e "  ${RED}✗ Backend failed (HTTP $HTTP)${NC}"
    SLOT_FAIL=1
  fi

  # Required: Airflow health 200 (webserver /health)
  HTTP_AIR=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$AIRFLOW_HEALTH" 2>/dev/null || echo "000")
  if [[ "$HTTP_AIR" == "200" ]]; then
    echo -e "  ${GREEN}✓ Airflow OK (200)${NC}"
  else
    echo -e "  ${RED}✗ Airflow failed (HTTP $HTTP_AIR)${NC}"
    SLOT_FAIL=1
  fi

  # Required: frontend responds 200 or 302
  HTTP_FE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 -L "$FRONTEND_URL" 2>/dev/null || echo "000")
  if [[ "$HTTP_FE" == "200" ]] || [[ "$HTTP_FE" == "302" ]]; then
    echo -e "  ${GREEN}✓ Frontend OK ($HTTP_FE)${NC}"
  else
    echo -e "  ${RED}✗ Frontend failed (HTTP $HTTP_FE)${NC}"
    SLOT_FAIL=1
  fi

  if [[ $SLOT_FAIL -eq 0 ]]; then
    echo -e "${GREEN}Slot $SLOT is ready for QA.${NC}"
  else
    echo -e "${RED}Slot $SLOT is NOT ready.${NC}"
    OVERALL_FAIL=1
  fi
  echo ""
done

if [[ $OVERALL_FAIL -eq 0 ]]; then
  echo -e "${GREEN}All specified slots are ready for QA.${NC}"
  exit 0
else
  echo -e "${RED}One or more slots failed verification.${NC}"
  exit 1
fi
