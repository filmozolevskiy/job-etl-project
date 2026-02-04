#!/bin/bash
# Deployment script for staging environments
#
# Usage:
#   ./scripts/deploy-staging.sh <slot_number> [branch]
#
# Examples:
#   ./scripts/deploy-staging.sh 1                    # Deploy current branch to slot 1
#   ./scripts/deploy-staging.sh 2 feature/my-branch  # Deploy specific branch to slot 2
#
# Prerequisites:
#   - SSH access to staging droplet
#   - Git repository cloned
#   - .env.staging-N file configured

set -euo pipefail

# Configuration
DROPLET_USER="deploy"
DROPLET_HOST="134.122.35.239"
BASE_DIR="/home/deploy"
REPO_URL="git@github.com:filmozolevskiy/job-etl-project.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
SLOT=${1:-}
BRANCH=${2:-$(git rev-parse --abbrev-ref HEAD)}

if [[ -z "$SLOT" ]]; then
    echo -e "${RED}Error: Slot number is required${NC}"
    echo "Usage: $0 <slot_number> [branch]"
    exit 1
fi

if [[ ! "$SLOT" =~ ^[1-9]$|^10$ ]]; then
    echo -e "${RED}Error: Slot must be between 1 and 10${NC}"
    exit 1
fi

# Calculate ports based on slot
CAMPAIGN_UI_PORT=$((5000 + SLOT))
AIRFLOW_PORT=$((8080 + SLOT))
FRONTEND_PORT=$((5173 + SLOT))

# Get current commit SHA
COMMIT_SHA=$(git rev-parse HEAD)
COMMIT_SHORT=$(git rev-parse --short HEAD)

echo -e "${GREEN}=== Deploying to staging-${SLOT} ===${NC}"
echo "Branch: $BRANCH"
echo "Commit: $COMMIT_SHORT"
echo "Campaign UI Port: $CAMPAIGN_UI_PORT"
echo "Airflow Port: $AIRFLOW_PORT"
echo ""

# Slot directory on the droplet
SLOT_DIR="${BASE_DIR}/staging-${SLOT}"
PROJECT_DIR="${SLOT_DIR}/job-search-project"
ENV_FILE="${SLOT_DIR}/.env.staging-${SLOT}"

# Use project SSH key when present (so no ~/.ssh/config required)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
  SSH_IDENTITY_FILE="${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh"
else
  SSH_IDENTITY_FILE=""
fi

# SSH and deploy
echo -e "${YELLOW}Connecting to staging droplet...${NC}"

SSH_CMD=(ssh)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")
SSH_CMD+=("${DROPLET_USER}@${DROPLET_HOST}" bash)

"${SSH_CMD[@]}" << EOF
set -euo pipefail

echo "=== Preparing slot directory ==="
mkdir -p "${SLOT_DIR}"
cd "${SLOT_DIR}"

# Clone or update repository
if [ -d "${PROJECT_DIR}" ]; then
    echo "Updating existing repository..."
    cd "${PROJECT_DIR}"
    git fetch origin
    git checkout "${BRANCH}"
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

# Write deployment metadata
echo "=== Writing deployment metadata ==="
cat > "${SLOT_DIR}/version.json" << VERSIONEOF
{
    "slot": ${SLOT},
    "branch": "${BRANCH}",
    "commit_sha": "${COMMIT_SHA}",
    "commit_short": "${COMMIT_SHORT}",
    "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "deployed_by": "${USER:-unknown}"
}
VERSIONEOF

# Export environment variables for docker compose
export STAGING_SLOT=${SLOT}
export DEPLOYED_SHA="${COMMIT_SHA}"
export DEPLOYED_BRANCH="${BRANCH}"
export CAMPAIGN_UI_PORT=${CAMPAIGN_UI_PORT}
export AIRFLOW_WEBSERVER_PORT=${AIRFLOW_PORT}
export FRONTEND_PORT=${FRONTEND_PORT}
export POSTGRES_NOOP_PORT=$((54000 + SLOT))

# Load environment file
set -a
source "${ENV_FILE}"
set +a

# Ensure staging postgres port stays slot-specific (env file must not override)
export POSTGRES_NOOP_PORT=$((54000 + SLOT))

echo "=== Stopping existing containers ==="
cd "${PROJECT_DIR}"
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" down --remove-orphans || true

echo "=== Building containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" build

echo "=== Running initial dbt (create marts including fact_jobs) ==="
cp -f dbt/profiles.staging.yml dbt/profiles.yml
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" run --rm --no-deps airflow-webserver \
  bash -c 'cd /opt/airflow/dbt && dbt run --project-dir . --target-path /tmp/dbt_target --log-path /tmp/dbt_logs'

echo "=== Starting containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" up -d

echo "=== Waiting for services to be healthy ==="
sleep 10

# Check service health
echo "=== Checking service health ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" ps

echo ""
echo "=== Deployment complete ==="
echo "Campaign UI: http://${DROPLET_HOST}:${CAMPAIGN_UI_PORT}"
echo "Airflow UI:  http://${DROPLET_HOST}:${AIRFLOW_PORT}"
echo ""
EOF

echo -e "${GREEN}=== Deployment successful ===${NC}"
echo ""
echo "Staging slot ${SLOT} deployed:"
echo "  Branch: ${BRANCH}"
echo "  Commit: ${COMMIT_SHORT}"
echo "  Campaign UI: http://${DROPLET_HOST}:${CAMPAIGN_UI_PORT}"
echo "  Airflow UI:  http://${DROPLET_HOST}:${AIRFLOW_PORT}"
echo ""
echo "Update project_documentation/staging-slots.md with deployment info."
