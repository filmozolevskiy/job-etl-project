#!/bin/bash
# Deployment script for dedicated production environment
#
# Usage:
#   ./scripts/deploy-production-dedicated.sh [branch]     # Normal deploy (default: main), pulls images from GHCR
#   ./scripts/deploy-production-dedicated.sh <commit-sha> # Rollback to specific commit
#   ./scripts/deploy-production-dedicated.sh --diagnose   # Run diagnostics only
#
# Build on droplet (no GHCR token needed; use when registry pull fails):
#   BUILD_ON_DROPLET=1 ./scripts/deploy-production-dedicated.sh main
#
# Examples:
#   ./scripts/deploy-production-dedicated.sh main
#   BUILD_ON_DROPLET=1 ./scripts/deploy-production-dedicated.sh main
#   ./scripts/deploy-production-dedicated.sh ed97cfd     # Rollback to this commit

set -euo pipefail

# Configuration
DROPLET_USER="deploy"
DROPLET_HOST="167.99.0.168"
BASE_DIR="/home/deploy"
REPO_URL="https://github.com/filmozolevskiy/job-etl-project.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Use project SSH key when present (needed for --diagnose)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${SSH_IDENTITY_FILE:-}" && -f "${SSH_IDENTITY_FILE}" ]]; then
  true
elif [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
  SSH_IDENTITY_FILE="${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh"
elif [[ -f "${HOME}/.ssh/id_rsa" ]]; then
  SSH_IDENTITY_FILE="${HOME}/.ssh/id_rsa"
else
  SSH_IDENTITY_FILE=""
fi

# Parse arguments
if [[ "${1:-}" == "--diagnose" ]]; then
  echo "Running production diagnostics via SSH..."
  SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
  SSH_CMD=(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no)
  [[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")
  exec "${SSH_CMD[@]}" "${DROPLET_USER}@${DROPLET_HOST}" 'bash -s' < "${SCRIPT_DIR}/diagnose-production.sh"
fi

# Support rollback by SHA: if arg looks like a commit SHA (7-40 hex chars), use as rollback target
if [[ "${1:-}" =~ ^[0-9a-f]{7,40}$ ]]; then
  ROLLBACK_SHA="$1"
  git fetch origin "${ROLLBACK_SHA}" 2>/dev/null || true
  COMMIT_SHA="$(git rev-parse "${ROLLBACK_SHA}" 2>/dev/null || echo "${ROLLBACK_SHA}")"
  COMMIT_SHORT="${COMMIT_SHA:0:7}"
  BRANCH="${COMMIT_SHA}"
  IS_ROLLBACK=1
else
  BRANCH="${1:-main}"
  COMMIT_SHA=$(git rev-parse "origin/${BRANCH}" 2>/dev/null || git rev-parse HEAD)
  COMMIT_SHORT=$(git rev-parse --short "${COMMIT_SHA}")
  IS_ROLLBACK=0
fi

echo -e "${GREEN}=== Deploying to dedicated production environment ===${NC}"
[[ "${IS_ROLLBACK}" -eq 1 ]] && echo -e "${YELLOW}(ROLLBACK MODE)${NC}"
echo "Branch/Ref: $BRANCH"
echo "Commit: $COMMIT_SHORT"
echo "Droplet: $DROPLET_HOST"
echo ""

# SSH and deploy
echo -e "${YELLOW}Connecting to production droplet...${NC}"

SSH_CMD=(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")
export REGISTRY="${REGISTRY:-ghcr.io}"
export IMAGE_NAME="${IMAGE_NAME:-filmozolevskiy/job-etl-project}"
# BUILD_ON_DROPLET=1: build images on droplet from repo (no GHCR pull). Use when registry pull fails or token is missing.
REMOTE_ENV="export BRANCH=${BRANCH} COMMIT_SHA=${COMMIT_SHA} COMMIT_SHORT=${COMMIT_SHORT} REGISTRY=${REGISTRY} IMAGE_NAME=${IMAGE_NAME} BUILD_ON_DROPLET=${BUILD_ON_DROPLET:-0}"

# Send token on first line of stdin, then script. Remote reads first line into GITHUB_TOKEN (avoids command-line escaping).
(
  printf '%s\n' "${GITHUB_TOKEN:-}"
  cat << 'EOF'
read -r GITHUB_TOKEN
set -euo pipefail
BASE_DIR="/home/deploy"
PROJECT_DIR="${BASE_DIR}/job-search-project"
ENV_FILE="${BASE_DIR}/.env.production"
REPO_URL="https://github.com/filmozolevskiy/job-etl-project.git"
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-filmozolevskiy/job-etl-project}"

echo "=== Preparing project directory ==="
mkdir -p "${BASE_DIR}"
cd "${BASE_DIR}"

# Backup current version before deploy (for rollback). Do this first, before we overwrite anything.
if [ -f "${BASE_DIR}/version.json" ]; then
  cp "${BASE_DIR}/version.json" "${BASE_DIR}/last-known-good.json"
  echo "Saved current version to last-known-good.json (rollback reference)"
fi

# Clone or update repository
if [ -d "${PROJECT_DIR}" ]; then
    echo "Updating existing repository..."
    cd "${PROJECT_DIR}"
    git fetch origin
    if [[ "${BRANCH}" =~ ^[0-9a-f]{7,40}$ ]]; then
        echo "Rollback: checking out commit ${BRANCH}"
        git checkout "${BRANCH}"
    else
        git checkout "${BRANCH}"
        git reset --hard "origin/${BRANCH}"
        git clean -fd
        git pull origin "${BRANCH}"
    fi
else
    echo "Cloning repository..."
    git clone "${REPO_URL}" job-search-project
    cd "${PROJECT_DIR}"
    git checkout "${BRANCH}"
fi

# Log in to registry on the droplet (skip when building on droplet)
if [ "${BUILD_ON_DROPLET:-0}" != "1" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
    echo "Logging in to GitHub Container Registry..."
    echo "${GITHUB_TOKEN}" | docker login ghcr.io -u filmozolevskiy --password-stdin
fi

# Verify environment file exists
if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: Environment file not found: ${ENV_FILE}"
    echo "Please create the environment file first."
    exit 1
fi

# Ensure dbt directories have correct permissions for the container user
mkdir -p "${PROJECT_DIR}/dbt/logs" "${PROJECT_DIR}/dbt/target"
chmod -R 777 "${PROJECT_DIR}/dbt/logs" "${PROJECT_DIR}/dbt/target"

# Write deployment metadata
echo "=== Writing deployment metadata ==="
cat > "${BASE_DIR}/version.json" << VERSIONEOF
{
    "environment": "production",
    "branch": "${BRANCH}",
    "commit_sha": "${COMMIT_SHA}",
    "commit_short": "${COMMIT_SHORT}",
    "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "deployed_by": "deployment-script"
}
VERSIONEOF

# Export environment variables for docker-compose
# When building on droplet use IMAGE_TAG=latest so built images are used; otherwise use commit SHA for registry pull
export ENVIRONMENT=production
export DEPLOYED_SHA="${COMMIT_SHA}"
export DEPLOYED_BRANCH="${BRANCH}"
export REGISTRY="${REGISTRY}"
export IMAGE_NAME="${IMAGE_NAME}"
if [ "${BUILD_ON_DROPLET:-0}" = "1" ]; then
  export IMAGE_TAG=latest
else
  export IMAGE_TAG="${COMMIT_SHA}"
fi

# Load environment file
set -a
source "${ENV_FILE}"
set +a

# All docker-compose commands must run from PROJECT_DIR
cd "${PROJECT_DIR}"
if [ "${BUILD_ON_DROPLET:-0}" = "1" ]; then
  echo "=== Building images on droplet (no registry pull) ==="
  docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" build
else
  echo "=== Pulling images from registry (REGISTRY=${REGISTRY} IMAGE_NAME=${IMAGE_NAME} IMAGE_TAG=${IMAGE_TAG}) ==="
  docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" pull
fi

echo "=== Stopping existing containers ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" down --remove-orphans || true

echo "=== Starting containers ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" up -d

echo "=== Waiting for services to be healthy ==="
sleep 15

# Check service health
echo "=== Checking service health ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" ps

echo ""
echo "Backend API: https://justapply.net"
echo "Airflow UI:  https://justapply.net/airflow/"
EOF
) | "${SSH_CMD[@]}" "${DROPLET_USER}@${DROPLET_HOST}" "${REMOTE_ENV}; bash -s"

echo -e "${GREEN}=== Deployment successful ===${NC}"
