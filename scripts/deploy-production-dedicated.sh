#!/bin/bash
# Deployment script for dedicated production environment
#
# Usage:
#   ./scripts/deploy-production-dedicated.sh [branch]
#   ./scripts/deploy-production-dedicated.sh --diagnose   # Run diagnostics only
#
# Examples:
#   ./scripts/deploy-production-dedicated.sh main

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
BRANCH=${1:-main}

# Get current commit SHA
COMMIT_SHA=$(git rev-parse HEAD)
COMMIT_SHORT=$(git rev-parse --short HEAD)

echo -e "${GREEN}=== Deploying to dedicated production environment ===${NC}"
echo "Branch: $BRANCH"
echo "Commit: $COMMIT_SHORT"
echo "Droplet: $DROPLET_HOST"
echo ""

# SSH and deploy
echo -e "${YELLOW}Connecting to production droplet...${NC}"

SSH_CMD=(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")
# Pass variables to the remote shell (REGISTRY, IMAGE_NAME, GITHUB_TOKEN required for docker pull from ghcr.io)
export REGISTRY="${REGISTRY:-ghcr.io}"
export IMAGE_NAME="${IMAGE_NAME:-filmozolevskiy/job-etl-project}"
SSH_CMD+=("${DROPLET_USER}@${DROPLET_HOST}" "export BRANCH=${BRANCH} COMMIT_SHA=${COMMIT_SHA} COMMIT_SHORT=${COMMIT_SHORT} REGISTRY=${REGISTRY} IMAGE_NAME=${IMAGE_NAME} GITHUB_TOKEN='${GITHUB_TOKEN:-}'; bash -s")

"${SSH_CMD[@]}" << 'EOF'
set -euo pipefail

# Note: These variables are now set inside the droplet shell
BASE_DIR="/home/deploy"
PROJECT_DIR="${BASE_DIR}/job-search-project"
ENV_FILE="${BASE_DIR}/.env.production"
REPO_URL="https://github.com/filmozolevskiy/job-etl-project.git"
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-filmozolevskiy/job-etl-project}"

echo "=== Preparing project directory ==="
mkdir -p "${BASE_DIR}"
cd "${BASE_DIR}"

# Clone or update repository
if [ -d "${PROJECT_DIR}" ]; then
    echo "Updating existing repository..."
    cd "${PROJECT_DIR}"
    git fetch origin
    git checkout "${BRANCH}"
    git reset --hard "origin/${BRANCH}"
    git clean -fd
    git pull origin "${BRANCH}"
else
    echo "Cloning repository..."
    git clone "${REPO_URL}" job-search-project
    cd "${PROJECT_DIR}"
    git checkout "${BRANCH}"
fi

# Log in to registry on the droplet
if [ -n "${GITHUB_TOKEN:-}" ]; then
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
export ENVIRONMENT=production
export DEPLOYED_SHA="${COMMIT_SHA}"
export DEPLOYED_BRANCH="${BRANCH}"
export REGISTRY="${REGISTRY}"
export IMAGE_NAME="${IMAGE_NAME}"

# Load environment file
set -a
source "${ENV_FILE}"
set +a

echo "=== Pulling images from registry ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" pull

echo "=== Stopping existing containers ==="
cd "${PROJECT_DIR}"
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" down --remove-orphans || true

echo "=== Starting containers ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" up -d

echo "=== Waiting for services to be healthy ==="
sleep 15

# Check service health
echo "=== Checking service health ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" ps

echo ""
echo "=== Deployment complete ==="
EOF

echo -e "${GREEN}=== Deployment successful ===${NC}"
