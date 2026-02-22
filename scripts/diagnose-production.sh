#!/bin/bash
# Diagnostic script for dedicated production environment.
# Run this ON the production droplet (or via SSH) to troubleshoot accessibility issues.
#
# Usage (from local machine):
#   ssh deploy@167.99.0.168 'bash -s' < ./scripts/diagnose-production.sh
#
# Or SSH to droplet first, then:
#   cd /home/deploy/job-search-project && ./scripts/diagnose-production.sh

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
  echo -e "   ${GREEN}✓${NC} Exists at ${ENV_FILE}"
  # Don't print contents (secrets)
else
  echo -e "   ${RED}✗ MISSING${NC} - ${ENV_FILE}"
  echo "   Action: Create .env.production with POSTGRES_*, FLASK_*, etc."
fi
echo ""

# 2. Check Docker
echo "2. Docker status:"
if command -v docker &>/dev/null; then
  echo -e "   ${GREEN}✓${NC} Docker installed"
  docker info &>/dev/null && echo -e "   ${GREEN}✓${NC} Docker daemon running" || echo -e "   ${RED}✗${NC} Docker daemon not running"
else
  echo -e "   ${RED}✗${NC} Docker not found"
fi
echo ""

# 3. Check production containers
echo "3. Production containers (docker ps -a --filter name=production):"
if command -v docker &>/dev/null; then
  docker ps -a --filter "name=production" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
  RUNNING=$(docker ps --filter "name=production" -q 2>/dev/null | wc -l)
  echo ""
  if [[ "${RUNNING}" -eq 0 ]]; then
    echo -e "   ${RED}No production containers are running.${NC}"
    echo "   Action: Run deployment: ./scripts/deploy-production-dedicated.sh"
  else
    echo -e "   ${GREEN}${RUNNING} container(s) running${NC}"
  fi
fi
echo ""

# 4. Check port 80
echo "4. Port 80 listener:"
if command -v ss &>/dev/null; then
  ss -tlnp 2>/dev/null | grep ':80 ' || echo -e "   ${RED}Nothing listening on port 80${NC}"
elif command -v netstat &>/dev/null; then
  netstat -tlnp 2>/dev/null | grep ':80 ' || echo -e "   ${RED}Nothing listening on port 80${NC}"
else
  echo "   (ss/netstat not available)"
fi
echo ""

# 5. Recent frontend/backend logs
echo "5. Recent logs (frontend, backend-api):"
if [[ -d "${PROJECT_DIR}" ]] && command -v docker &>/dev/null; then
  cd "${PROJECT_DIR}" 2>/dev/null || true
  for svc in production-frontend production-backend-api; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${svc}$"; then
      echo "   --- ${svc} (last 5 lines) ---"
      docker logs "${svc}" --tail 5 2>&1 | sed 's/^/   /'
    fi
  done
else
  echo "   (Cannot read logs)"
fi
echo ""

# 6. Recommendation
echo "6. Recommended actions:"
echo "   If containers are down: cd ${PROJECT_DIR} && docker-compose -f docker-compose.yml -f docker-compose.production.yml -p production up -d"
echo "   If .env.production is missing: Create it with required variables (see .env.example)"
echo "   Full redeploy: ./scripts/deploy-production-dedicated.sh main"
echo ""
