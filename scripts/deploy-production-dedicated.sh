#!/bin/bash
# Deployment script for dedicated production environment
#
# Usage:
#   ./scripts/deploy-production-dedicated.sh [branch]
#
# Examples:
#   ./scripts/deploy-production-dedicated.sh main
#
# Prerequisites:
#   - SSH access to production droplet
#   - Git repository cloned
#   - .env.production file configured on the droplet

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

# Parse arguments
BRANCH=${1:-main}

# Get current commit SHA
COMMIT_SHA=$(git rev-parse HEAD)
COMMIT_SHORT=$(git rev-parse --short HEAD)

echo -e "${GREEN}=== Deploying to dedicated production environment ===${NC}"
echo "Branch: $BRANCH"
echo "Commit: $COMMIT_SHORT"
echo "Droplet: $DROPLET_HOST"
echo ""

# Project directory on the droplet
PROJECT_DIR="${BASE_DIR}/job-search-project"
ENV_FILE="${BASE_DIR}/.env.production"

# Use project SSH key when present
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
  SSH_IDENTITY_FILE="${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh"
else
  SSH_IDENTITY_FILE=""
fi

# SSH and deploy
echo -e "${YELLOW}Connecting to production droplet...${NC}"

SSH_CMD=(ssh -o StrictHostKeyChecking=no)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")
SSH_CMD+=("${DROPLET_USER}@${DROPLET_HOST}" bash)

"${SSH_CMD[@]}" << EOF
set -euo pipefail

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
    # Note: This requires SSH key for GitHub to be present on the droplet or use HTTPS with token
    # For now, we'll assume the droplet has access or use a workaround
    git clone "${REPO_URL}" job-search-project
    cd "${PROJECT_DIR}"
    git checkout "${BRANCH}"
fi

# Verify environment file exists
if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: Environment file not found: ${ENV_FILE}"
    echo "Please create the environment file first."
    exit 1
fi

# Write deployment metadata
echo "=== Writing deployment metadata ==="
cat > "${BASE_DIR}/version.json" << VERSIONEOF
{
    "environment": "production",
    "branch": "${BRANCH}",
    "commit_sha": "${COMMIT_SHA}",
    "commit_short": "${COMMIT_SHORT}",
    "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "deployed_by": "${USER:-unknown}"
}
VERSIONEOF

# Export environment variables for docker-compose
export ENVIRONMENT=production
export DEPLOYED_SHA="${COMMIT_SHA}"
export DEPLOYED_BRANCH="${BRANCH}"

# Load environment file
set -a
source "${ENV_FILE}"
set +a

echo "=== Stopping existing containers ==="
cd "${PROJECT_DIR}"
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" down --remove-orphans || true

echo "=== Building containers ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" build

echo "=== Running initial dbt ==="
# Ensure profiles.yml is correct for production
# cp -f dbt/profiles.production.yml dbt/profiles.yml 
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" run --rm \
  -e POSTGRES_HOST="\${POSTGRES_HOST}" \
  -e POSTGRES_PORT="\${POSTGRES_PORT}" \
  -e POSTGRES_USER="\${POSTGRES_USER}" \
  -e POSTGRES_PASSWORD="\${POSTGRES_PASSWORD}" \
  -e POSTGRES_DB="\${POSTGRES_DB}" \
  --no-deps airflow-webserver \
  bash -c 'cd /opt/airflow/dbt && dbt run --target dev --profiles-dir . --target-path /tmp/dbt_target --log-path /tmp/dbt_logs'

echo "=== Starting containers ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" up -d

echo "=== Waiting for services to be healthy ==="
sleep 15

# Check service health
echo "=== Checking service health ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" ps

echo ""
echo "=== Deployment complete ==="
echo "Production UI: http://${DROPLET_HOST}"
echo ""
EOF

echo -e "${GREEN}=== Deployment successful ===${NC}"
