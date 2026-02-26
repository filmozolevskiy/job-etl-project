#!/bin/bash
# Roll back production to the last known good deployment.
#
# Usage:
#   ./scripts/rollback-production.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Configuration
DROPLET_USER="deploy"
DROPLET_HOST="167.99.0.168"
BASE_DIR="/home/deploy"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

if [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
  SSH_IDENTITY_FILE="${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh"
elif [[ -f "${HOME}/.ssh/id_rsa" ]]; then
  SSH_IDENTITY_FILE="${HOME}/.ssh/id_rsa"
else
  SSH_IDENTITY_FILE=""
fi

SSH_CMD=(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")

echo -e "${YELLOW}=== Production Rollback ===${NC}"
echo "Fetching last-known-good commit from droplet..."

LAST_KNOWN_JSON=$("${SSH_CMD[@]}" "${DROPLET_USER}@${DROPLET_HOST}" \
  "cat ${BASE_DIR}/last-known-good.json 2>/dev/null" || true)

if [[ -z "${LAST_KNOWN_JSON}" ]]; then
  echo -e "${RED}ERROR: last-known-good.json not found on droplet.${NC}"
  echo "Manual recovery: deploy a specific commit with:"
  echo "  ./scripts/deploy-production.sh <commit-sha>"
  exit 1
fi

# Extract commit_sha
if command -v jq &>/dev/null; then
  COMMIT_SHA=$(echo "${LAST_KNOWN_JSON}" | jq -r '.commit_sha // empty')
else
  COMMIT_SHA=$(echo "${LAST_KNOWN_JSON}" | grep -o '"commit_sha"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
fi

if [[ -z "${COMMIT_SHA}" ]]; then
  echo -e "${RED}ERROR: Could not parse commit_sha from last-known-good.json${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Last known good: ${COMMIT_SHA}${NC}"
echo ""
echo "Rolling back production to this commit..."
echo ""

cd "${REPO_ROOT}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-${REGISTRY_TOKEN:-}}"
if "${SCRIPT_DIR}/deploy-production.sh" "${COMMIT_SHA}"; then
    echo ""
    echo -e "${GREEN}=== ✓ Rollback complete ===${NC}"
else
    echo -e "${RED}✗ Rollback failed.${NC}"
    exit 1
fi
