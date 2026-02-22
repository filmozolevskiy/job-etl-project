#!/bin/bash
# Roll back production to the last known good deployment.
#
# This script reads the last-known-good.json from the production droplet
# (saved before each deploy by deploy-production-dedicated.sh) and
# re-deploys using that commit SHA.
#
# Usage:
#   ./scripts/rollback-production.sh
#
# Prerequisites:
#   - SSH access to production droplet
#   - GITHUB_TOKEN or REGISTRY_TOKEN (for docker pull from ghcr.io)
#   - At least one successful deploy must have run (to populate last-known-good.json)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Same config as deploy-production-dedicated.sh
DROPLET_USER="deploy"
DROPLET_HOST="167.99.0.168"
BASE_DIR="/home/deploy"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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
  echo "Either production has never been deployed successfully, or the file was removed."
  echo "Manual recovery: deploy a specific commit with:"
  echo "  ./scripts/deploy-production-dedicated.sh <commit-sha>"
  exit 1
fi

# Extract commit_sha (works with or without jq)
if command -v jq &>/dev/null; then
  COMMIT_SHA=$(echo "${LAST_KNOWN_JSON}" | jq -r '.commit_sha // empty')
else
  COMMIT_SHA=$(echo "${LAST_KNOWN_JSON}" | grep -o '"commit_sha"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
fi

if [[ -z "${COMMIT_SHA}" ]]; then
  echo -e "${RED}ERROR: Could not parse commit_sha from last-known-good.json${NC}"
  echo "Content: ${LAST_KNOWN_JSON}"
  exit 1
fi

echo -e "${GREEN}Last known good: ${COMMIT_SHA}${NC}"
echo ""
echo "Rolling back production to this commit..."
echo ""

# Pass GITHUB_TOKEN for registry pull (same as deploy script)
cd "${REPO_ROOT}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-${REGISTRY_TOKEN:-}}"
"${SCRIPT_DIR}/deploy-production-dedicated.sh" "${COMMIT_SHA}"

echo ""
echo -e "${GREEN}=== Rollback complete ===${NC}"
