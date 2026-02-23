#!/bin/bash
# Release staging slot(s) in the registry and tear down containers on the staging droplet.
# 1. Call Staging API POST /api/staging/slots/<id>/release (requires STAGING_ADMIN_JWT).
# 2. SSH to staging droplet and run: docker compose -p staging-<N> down.
#
# Usage: ./scripts/teardown-staging.sh <slot> [slot ...]
# Example: ./scripts/teardown-staging.sh 2
# Example: ./scripts/teardown-staging.sh 1 3 5

set -euo pipefail

DROPLET_USER="${DROPLET_USER:-deploy}"
DROPLET_HOST="${STAGING_DROPLET_HOST:-134.122.35.239}"
BASE_DIR="/home/deploy"
BASE_URL="${BASE_URL:-https://justapply.net}"
JWT="${STAGING_ADMIN_JWT:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
  SSH_IDENTITY_FILE="${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh"
else
  SSH_IDENTITY_FILE=""
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <slot> [slot ...]"
  echo "  slot: 1-10. Release slot in registry and run 'docker compose -p staging-<N> down' on droplet."
  echo "Requires STAGING_ADMIN_JWT for API release. SSH to droplet for teardown."
  exit 1
fi

SSH_CMD=(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")

for SLOT in "$@"; do
  if [[ ! "$SLOT" =~ ^[1-9]$|^10$ ]]; then
    echo -e "${RED}Invalid slot: $SLOT (must be 1-10). Skipping.${NC}"
    continue
  fi

  echo -e "${YELLOW}=== Releasing and tearing down staging-${SLOT} ===${NC}"

  # 1. Release slot in registry (API)
  if [[ -n "$JWT" ]]; then
    HTTP=$(curl -s -w "%{http_code}" -o /tmp/teardown-release-"${SLOT}".json \
      -X POST \
      -H "Authorization: Bearer $JWT" \
      -H "Content-Type: application/json" \
      "$BASE_URL/api/staging/slots/$SLOT/release")
    if [[ "$HTTP" -ge 200 && "$HTTP" -lt 300 ]]; then
      echo -e "${GREEN}Slot $SLOT released in registry.${NC}"
    else
      echo -e "${RED}Release API failed for slot $SLOT (HTTP $HTTP). Continuing to teardown.${NC}"
    fi
  else
    echo "STAGING_ADMIN_JWT not set; skipping API release. Release slot $SLOT manually at $BASE_URL/staging"
  fi

  # 2. Teardown containers on droplet
  PROJECT_DIR="${BASE_DIR}/staging-${SLOT}/job-search-project"
  echo "Stopping containers for staging-${SLOT} on droplet..."
  if "${SSH_CMD[@]}" "${DROPLET_USER}@${DROPLET_HOST}" \
    "cd ${PROJECT_DIR} 2>/dev/null && docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} down --remove-orphans || true"; then
    echo -e "${GREEN}Teardown completed for staging-${SLOT}.${NC}"
  else
    echo -e "${YELLOW}SSH or teardown failed for slot $SLOT (dir may not exist).${NC}"
  fi
  echo ""
done

echo -e "${GREEN}Done.${NC}"
