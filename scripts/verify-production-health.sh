#!/bin/bash
# Verify production health after deploy. Exits 0 only if backend health returns 200.
# Usage: ./scripts/verify-production-health.sh [base_url]
# Example: ./scripts/verify-production-health.sh
# Example: ./scripts/verify-production-health.sh https://justapply.net

set -euo pipefail

BASE_URL="${1:-https://justapply.net}"
HEALTH_URL="${BASE_URL%/}/api/health"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Checking production health: $HEALTH_URL"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 15 "$HEALTH_URL" 2>/dev/null || echo "000")

if [[ "$HTTP" == "200" ]]; then
  echo -e "${GREEN}Production health OK (200).${NC}"
  exit 0
fi

echo -e "${RED}Production health check failed (HTTP $HTTP).${NC}"
exit 1
