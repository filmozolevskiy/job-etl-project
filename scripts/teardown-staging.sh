#!/bin/bash
# Release staging slot(s) in the registry and tear down containers on the staging droplet.
# Uses direct DB update on production droplet (same approach as deploy-staging for claiming).
# No JWT required.
#
# Usage: ./scripts/teardown-staging.sh <slot> [slot ...]

set -euo pipefail

DROPLET_USER="${DROPLET_USER:-deploy}"
STAGING_DROPLET="${STAGING_DROPLET_HOST:-134.122.35.239}"
PRODUCTION_DROPLET="${PRODUCTION_DROPLET_HOST:-167.99.0.168}"
BASE_DIR="/home/deploy"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <slot> [slot ...]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
  SSH_IDENTITY_FILE="${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh"
elif [[ -f "${HOME}/.ssh/id_rsa" ]]; then
  SSH_IDENTITY_FILE="${HOME}/.ssh/id_rsa"
else
  SSH_IDENTITY_FILE=""
fi

SSH_CMD=(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")

for SLOT in "$@"; do
  if [[ ! "$SLOT" =~ ^[1-9]$|^10$ ]]; then
    echo -e "${RED}Invalid slot: $SLOT (must be 1-10). Skipping.${NC}"
    continue
  fi

  echo -e "${YELLOW}=== Releasing and tearing down staging-${SLOT} ===${NC}"

  PROJECT_DIR="${BASE_DIR}/staging-${SLOT}/job-search-project"

  # 1. Release slot in registry (direct DB update on production droplet, same pattern as deploy-staging)
  PROD_ENV="${BASE_DIR}/.env.production"
  if "${SSH_CMD[@]}" "${DROPLET_USER}@${PRODUCTION_DROPLET}" bash -s << EOF
set -e
[[ -f "${PROD_ENV}" ]] || exit 1
set -a
source "${PROD_ENV}"
set +a
docker run --rm \
  -e PGPASSWORD="\${POSTGRES_PASSWORD}" \
  -e PGHOST="\${POSTGRES_HOST}" \
  -e PGPORT="\${POSTGRES_PORT}" \
  -e PGUSER="\${POSTGRES_USER}" \
  -e PGDATABASE="\${POSTGRES_DB:-job_search_production}" \
  -e PGSSLMODE=require \
  postgres:15 \
  psql -c "
  UPDATE marts.staging_slots
  SET status = 'Available',
      owner = NULL,
      branch = NULL,
      issue_id = NULL,
      deployed_at = NULL,
      purpose = NULL,
      updated_at = CURRENT_TIMESTAMP
  WHERE slot_id = ${SLOT};
"
EOF
  then
    echo -e "  ${GREEN}✓ Slot $SLOT released in registry.${NC}"
  else
    echo -e "  ${YELLOW}  Could not release slot $SLOT in registry (env file missing or psql failed).${NC}"
  fi

  # 2. Teardown containers on staging droplet
  echo "  Stopping containers on droplet..."
  if "${SSH_CMD[@]}" "${DROPLET_USER}@${STAGING_DROPLET}" \
    "cd ${PROJECT_DIR} 2>/dev/null && docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} down --remove-orphans || true"; then
    echo -e "  ${GREEN}✓ Teardown completed for staging-${SLOT}.${NC}"
  else
    echo -e "  ${RED}✗ SSH or teardown failed for slot $SLOT.${NC}"
  fi
  echo ""
done

echo -e "${GREEN}=== ✓ Teardown process complete ===${NC}"
