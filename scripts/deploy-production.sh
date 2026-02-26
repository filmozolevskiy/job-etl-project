#!/bin/bash
# Deployment script for dedicated production environment.
#
# Usage:
#   ./scripts/deploy-production.sh [branch]     # Normal deploy (default: main)
#   ./scripts/deploy-production.sh <commit-sha> # Rollback to specific commit
#   ./scripts/deploy-production.sh --diagnose   # Run diagnostics only

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

# Use project SSH key when present
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

# Parse arguments
if [[ "${1:-}" == "--diagnose" ]]; then
  echo "Running production diagnostics via SSH..."
  exec "${SSH_CMD[@]}" "${DROPLET_USER}@${DROPLET_HOST}" 'bash -s' < "${SCRIPT_DIR}/diagnose-production.sh"
fi

# Support rollback by SHA
if [[ "${1:-}" =~ ^[0-9a-f]{7,40}$ ]]; then
  COMMIT_SHA="$1"
  git fetch origin "${COMMIT_SHA}" 2>/dev/null || true
  COMMIT_SHA="$(git rev-parse "${COMMIT_SHA}" 2>/dev/null || echo "${COMMIT_SHA}")"
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

export REGISTRY="${REGISTRY:-ghcr.io}"
export IMAGE_NAME="${IMAGE_NAME:-filmozolevskiy/job-etl-project}"
REMOTE_ENV="export BRANCH=${BRANCH} COMMIT_SHA=${COMMIT_SHA} COMMIT_SHORT=${COMMIT_SHORT} REGISTRY=${REGISTRY} IMAGE_NAME=${IMAGE_NAME} BUILD_ON_DROPLET=${BUILD_ON_DROPLET:-0}"

(
  echo 'read -r GITHUB_TOKEN'
  printf '%s\n' "${GITHUB_TOKEN:-}"
  cat << 'EOF'
set -euo pipefail
BASE_DIR="/home/deploy"
PROJECT_DIR="${BASE_DIR}/job-search-project"
ENV_FILE="${BASE_DIR}/.env.production"
REPO_URL="https://github.com/filmozolevskiy/job-etl-project.git"

echo "=== Preparing project directory ==="
mkdir -p "${BASE_DIR}"
cd "${BASE_DIR}"

if [ -f "${BASE_DIR}/version.json" ]; then
  cp "${BASE_DIR}/version.json" "${BASE_DIR}/last-known-good.json"
  echo "  ✓ Saved current version to last-known-good.json"
fi

if [ -d "${PROJECT_DIR}" ]; then
    echo "Updating existing repository..."
    cd "${PROJECT_DIR}"
    git fetch origin
    if [[ "${BRANCH}" =~ ^[0-9a-f]{7,40}$ ]]; then
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
echo "  ✓ Repository updated."

if [ "${BUILD_ON_DROPLET:-0}" != "1" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
    echo "Logging in to GitHub Container Registry..."
    echo "${GITHUB_TOKEN}" | docker login ghcr.io -u filmozolevskiy --password-stdin
fi

if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: Environment file not found: ${ENV_FILE}"
    exit 1
fi

mkdir -p "${PROJECT_DIR}/dbt/logs" "${PROJECT_DIR}/dbt/target"
chmod -R 777 "${PROJECT_DIR}/dbt/logs" "${PROJECT_DIR}/dbt/target"

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

set a
source "${ENV_FILE}"
set +a

cd "${PROJECT_DIR}"
if [ "${BUILD_ON_DROPLET:-0}" = "1" ]; then
  echo "=== Building images on droplet ==="
  docker compose -f docker-compose.yml -f docker-compose.production.yml -p "production" build
else
  echo "=== Pulling images from registry ==="
  docker compose -f docker-compose.yml -f docker-compose.production.yml -p "production" pull
fi

echo "=== Stopping existing containers ==="
docker compose -f docker-compose.yml -f docker-compose.production.yml -p "production" down --remove-orphans || true

echo "=== Running initial dbt ==="
cp -f dbt/profiles.staging.yml dbt/profiles.yml
docker compose -f docker-compose.yml -f docker-compose.production.yml -p "production" run --rm --no-deps \
  -v "${PROJECT_DIR}/dbt:/opt/airflow/dbt" \
  airflow-webserver bash -c 'cd /opt/airflow/dbt && dbt run --project-dir . --target-path /tmp/dbt_target --log-path /tmp/dbt_logs' \
  || echo "WARNING: dbt run had errors."

echo "=== Starting containers ==="
docker compose -f docker-compose.yml -f docker-compose.production.yml -p "production" up -d
echo "  ✓ Containers started."

sleep 15
docker compose -f docker-compose.yml -f docker-compose.production.yml -p "production" ps
EOF
) | "${SSH_CMD[@]}" "${DROPLET_USER}@${DROPLET_HOST}" "${REMOTE_ENV}; bash -s"

echo ""
echo -e "${GREEN}=== ✓ Deployment successful ===${NC}"
echo ""
echo -e "${YELLOW}=== Verifying production health ===${NC}"
PROD_URL="${PRODUCTION_URL:-https://justapply.net}"
if bash "${SCRIPT_DIR}/verify-production-health.sh" "$PROD_URL"; then
  echo -e "${GREEN}✓ Production is healthy. Deploy complete.${NC}"
else
  echo -e "${RED}✗ Production health check failed.${NC}"
  exit 1
fi
