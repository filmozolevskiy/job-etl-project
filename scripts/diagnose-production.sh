#!/bin/bash
# Diagnostic script for dedicated production environment.
#
# Usage:
#   ./scripts/diagnose-production.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BASE_DIR="${BASE_DIR:-/home/deploy}"
PROJECT_DIR="${BASE_DIR}/job-search-project"
ENV_FILE="${BASE_DIR}/.env.production"

echo -e "${YELLOW}=== Production Environment Diagnostics ===${NC}"
echo ""

# 1. Check environment file
echo "1. Environment file (.env.production):"
if [[ -f "${ENV_FILE}" ]]; then
  echo -e "   ${GREEN}✓ Exists at ${ENV_FILE}${NC}"
else
  echo -e "   ${RED}✗ MISSING - ${ENV_FILE}${NC}"
fi
echo ""

# 2. Check Docker
echo "2. Docker status:"
if command -v docker &>/dev/null; then
  echo -e "   ${GREEN}✓ Docker installed${NC}"
  if docker info &>/dev/null; then
    echo -e "   ${GREEN}✓ Docker daemon running${NC}"
  else
    echo -e "   ${RED}✗ Docker daemon not running${NC}"
  fi
else
  echo -e "   ${RED}✗ Docker not found${NC}"
fi
echo ""

# 3. Check production containers
echo "3. Production containers:"
if command -v docker &>/dev/null; then
  docker ps -a --filter "name=production" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
  RUNNING=$(docker ps --filter "name=production" -q 2>/dev/null | wc -l)
  echo ""
  if [[ "${RUNNING}" -eq 0 ]]; then
    echo -e "   ${RED}No production containers are running.${NC}"
  else
    echo -e "   ${GREEN}${RUNNING} container(s) running${NC}"
  fi
fi
echo ""

# 4. Check port 80
echo "4. Port 80 listener:"
if command -v ss &>/dev/null; then
  if ss -tlnp 2>/dev/null | grep -q ':80 '; then
    echo -e "   ${GREEN}✓ Something is listening on port 80${NC}"
  else
    echo -e "   ${RED}✗ Nothing listening on port 80${NC}"
  fi
elif command -v netstat &>/dev/null; then
  if netstat -tlnp 2>/dev/null | grep -q ':80 '; then
    echo -e "   ${GREEN}✓ Something is listening on port 80${NC}"
  else
    echo -e "   ${RED}✗ Nothing listening on port 80${NC}"
  fi
else
  echo "   (ss/netstat not available)"
fi
echo ""

# 5. Recent logs
echo "5. Recent logs (last 5 lines):"
if [[ -d "${PROJECT_DIR}" ]] && command -v docker &>/dev/null; then
  for svc in production-frontend production-backend-api; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${svc}$"; then
      echo "   --- ${svc} ---"
      docker logs "${svc}" --tail 5 2>&1 | sed 's/^/   /'
    fi
  done
else
  echo "   (Cannot read logs)"
fi
echo ""

echo -e "${GREEN}=== ✓ Diagnostics complete ===${NC}"
