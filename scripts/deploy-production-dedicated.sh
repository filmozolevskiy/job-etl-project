#!/bin/bash
# Deployment script for dedicated production environment
#
# Usage:
#   ./scripts/deploy-production-dedicated.sh [branch]
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

# Use project SSH key when present
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
  SSH_IDENTITY_FILE="${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh"
elif [[ -f "${HOME}/.ssh/id_rsa" ]]; then
  SSH_IDENTITY_FILE="${HOME}/.ssh/id_rsa"
else
  SSH_IDENTITY_FILE=""
fi

# SSH and deploy
echo -e "${YELLOW}Connecting to production droplet...${NC}"

SSH_CMD=(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")
# Pass variables to the remote shell
SSH_CMD+=("${DROPLET_USER}@${DROPLET_HOST}" "export BRANCH=${BRANCH} COMMIT_SHA=${COMMIT_SHA} COMMIT_SHORT=${COMMIT_SHORT}; bash -s")

"${SSH_CMD[@]}" << 'EOF'
set -euo pipefail

# Note: These variables are now set inside the droplet shell
BASE_DIR="/home/deploy"
PROJECT_DIR="${BASE_DIR}/job-search-project"
ENV_FILE="${BASE_DIR}/.env.production"
REPO_URL="https://github.com/filmozolevskiy/job-etl-project.git"

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
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" run --rm \
  -e POSTGRES_HOST="${POSTGRES_HOST}" \
  -e POSTGRES_PORT="${POSTGRES_PORT}" \
  -e POSTGRES_USER="${POSTGRES_USER}" \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -e POSTGRES_DB="${POSTGRES_DB}" \
  --no-deps airflow-webserver \
  bash -c 'cd /opt/airflow/dbt && dbt run --target dev --profiles-dir . --target-path /tmp/dbt_target --log-path /tmp/dbt_logs'

echo "=== Running custom migrations ==="
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p "production" run --rm \
  -e DB_HOST="${POSTGRES_HOST}" \
  -e DB_PORT="${POSTGRES_PORT}" \
  -e DB_USER="${POSTGRES_USER}" \
  -e DB_PASSWORD="${POSTGRES_PASSWORD}" \
  -e DB_NAME="${POSTGRES_DB}" \
  -v /home/deploy/job-search-project/scripts:/opt/airflow/scripts \
  -v /home/deploy/job-search-project/docker:/opt/airflow/docker \
  --no-deps airflow-webserver \
  bash -c 'cd /opt/airflow && python scripts/run_migrations.py --verbose'

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
