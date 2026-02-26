#!/bin/bash
# Deployment script for staging environments.
# Clones/updates the repo on the droplet, builds containers, runs dbt, and seeds admin user.
#
# Usage:
#   ./scripts/deploy-staging.sh <slot_number> [branch]
#
# Examples:
#   ./scripts/deploy-staging.sh 1                    # Deploy current branch to slot 1
#   ./scripts/deploy-staging.sh 2 feature/my-branch  # Deploy specific branch to slot 2

set -euo pipefail

# Configuration
DROPLET_USER="deploy"
DROPLET_HOST="${STAGING_DROPLET_HOST:-134.122.35.239}"
PRODUCTION_DROPLET="${PRODUCTION_DROPLET_HOST:-167.99.0.168}"
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

# Optional: pass through to slot registry (per .cursorrules: branch, issue_id, purpose, deployed_at).
DEPLOY_ISSUE_ID="${ISSUE_ID:-$(echo "$BRANCH" | grep -oE 'JOB-[0-9]+' || echo '')}"
DEPLOY_PURPOSE="${PURPOSE:-QA: ${DEPLOY_ISSUE_ID} — Deployed via deploy-staging.sh}"
PY_PURPOSE=$(printf '%s' "$DEPLOY_PURPOSE" | sed 's/\\/\\\\/g; s/"/\\"/g')

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
echo "Backend API Port: $CAMPAIGN_UI_PORT"
echo "Airflow Port: $AIRFLOW_PORT"
echo ""

# Slot directory on the droplet
SLOT_DIR="${BASE_DIR}/staging-${SLOT}"
PROJECT_DIR="${SLOT_DIR}/job-search-project"
ENV_FILE="${SLOT_DIR}/.env.staging-${SLOT}"

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

# SSH and deploy
echo -e "${YELLOW}Connecting to staging droplet...${NC}"

SSH_CMD=(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")

"${SSH_CMD[@]}" "${DROPLET_USER}@${DROPLET_HOST}" bash << EOF
set -euo pipefail

echo "=== Preparing slot directory ==="
mkdir -p "${SLOT_DIR}"
cd "${SLOT_DIR}"

# Clone or update repository
if [ -d "${PROJECT_DIR}" ]; then
    echo "Updating existing repository..."
    cd "${PROJECT_DIR}"
    git fetch origin
    git reset --hard
    git clean -fd || true
    git checkout -B "${BRANCH}" "origin/${BRANCH}"
else
    echo "Cloning repository..."
    git clone "${REPO_URL}" job-search-project
    cd "${PROJECT_DIR}"
    git checkout "${BRANCH}"
fi
echo "✓ Repository updated."

# Verify environment file exists
if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: Environment file not found: ${ENV_FILE}"
    echo "Please run provision_staging_slot.sh first."
    exit 1
fi

# Copy slot env into project dir
rm -f "${PROJECT_DIR}/.env.staging"
cp -f "${ENV_FILE}" "${PROJECT_DIR}/.env.staging"

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

# Load environment file
set -a
source "${ENV_FILE}"
set +a

# Standardize credentials for all stagings: admin/admin123
export AIRFLOW_PASSWORD=admin123
export AIRFLOW_API_PASSWORD=admin123
export AIRFLOW_API_USERNAME=admin
export AIRFLOW_USERNAME=admin
sed -i.bak -e 's/^AIRFLOW_PASSWORD=.*/AIRFLOW_PASSWORD=admin123/' \
    -e 's/^AIRFLOW_API_PASSWORD=.*/AIRFLOW_API_PASSWORD=admin123/' \
    -e 's/^AIRFLOW_API_USERNAME=.*/AIRFLOW_API_USERNAME=admin/' \
    -e 's/^AIRFLOW_USERNAME=.*/AIRFLOW_USERNAME=admin/' "${ENV_FILE}" 2>/dev/null || true
grep -q '^AIRFLOW_PASSWORD=' "${ENV_FILE}" || echo 'AIRFLOW_PASSWORD=admin123' >> "${ENV_FILE}"
grep -q '^AIRFLOW_API_PASSWORD=' "${ENV_FILE}" || echo 'AIRFLOW_API_PASSWORD=admin123' >> "${ENV_FILE}"

# Export environment variables for docker compose
export STAGING_SLOT=${SLOT}
export DEPLOYED_SHA="${COMMIT_SHA}"
export DEPLOYED_BRANCH="${BRANCH}"
export DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export CAMPAIGN_UI_PORT=${CAMPAIGN_UI_PORT}
export AIRFLOW_WEBSERVER_PORT=${AIRFLOW_PORT}
export FRONTEND_PORT=${FRONTEND_PORT}
export POSTGRES_NOOP_PORT=$((54000 + SLOT))

echo "=== Stopping existing containers ==="
cd "${PROJECT_DIR}"
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" down --remove-orphans || true

echo "=== Building containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" build
echo "✓ Containers built."

echo "=== Running initial dbt (create marts) ==="
cp -f dbt/profiles.staging.yml dbt/profiles.yml
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" run --rm --no-deps airflow-webserver \
  bash -c 'cd /opt/airflow/dbt && dbt run --project-dir . --target-path /tmp/dbt_target --log-path /tmp/dbt_logs' || echo "WARNING: dbt run had errors."

echo "=== Ensuring Airflow logs dir is writable ==="
mkdir -p "${PROJECT_DIR}/airflow/logs"
chmod -R 777 "${PROJECT_DIR}/airflow/logs" || true

echo "=== Starting containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" up -d
echo "✓ Containers started."

echo "=== Verifying backend is up ==="
BACKEND_OK=0
for i in {1..5}; do
  if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${CAMPAIGN_UI_PORT}/api/health" | grep -q 200; then
    echo "  ✓ Backend health OK (200)"
    BACKEND_OK=1
    break
  fi
  echo "  Waiting for backend... (\$i/5)"
  sleep 3
done
if [ "\$BACKEND_OK" -ne 1 ]; then
  echo "ERROR: Backend did not respond with 200 after 5 attempts."
  exit 1
fi

echo "=== Seeding admin user ==="
if [ -f "${PROJECT_DIR}/docker/init/19_seed_admin_user.sql" ]; then
  docker run --rm \
    -v "${PROJECT_DIR}/docker/init:/sql:ro" \
    -e PGPASSWORD="\${POSTGRES_PASSWORD}" \
    -e PGHOST="\${POSTGRES_HOST}" \
    -e PGPORT="\${POSTGRES_PORT}" \
    -e PGUSER="\${POSTGRES_USER}" \
    -e PGDATABASE="\${POSTGRES_DB}" \
    -e PGSSLMODE=require \
    postgres:15 \
    psql -f /sql/19_seed_admin_user.sql \
  && echo "  ✓ Admin user seeded." || echo "  WARNING: Admin seed failed."
fi

echo "=== Ensuring Airflow admin is admin/admin123 ==="
echo "  Waiting for Airflow webserver to be ready..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  if docker exec staging-${SLOT}-airflow-webserver airflow users list 2>/dev/null | grep -q admin; then
    echo "  Airflow ready, resetting admin password..."
    docker exec staging-${SLOT}-airflow-webserver airflow users delete -u admin 2>/dev/null || true
    break
  fi
  sleep 5
done
for i in 1 2 3 4 5 6 7 8 9 10; do
  if docker exec staging-${SLOT}-airflow-webserver airflow users create -u admin -p admin123 -f admin -l admin -r Admin -e admin@example.com 2>/dev/null; then
    echo "  ✓ Airflow admin set to admin/admin123."
    break
  fi
  sleep 5
done

echo "=== Updating nginx config ==="
if [ -f "${PROJECT_DIR}/infra/nginx/staging-multi.conf" ]; then
  sudo cp -f "${PROJECT_DIR}/infra/nginx/staging-multi.conf" /etc/nginx/sites-available/staging-multi
  sudo ln -sf /etc/nginx/sites-available/staging-multi /etc/nginx/sites-enabled/staging-multi
  sudo nginx -t && sudo systemctl reload nginx && echo "  ✓ Nginx reloaded." || echo "  WARNING: Nginx reload failed."
fi

EOF

# Update staging slot registry (on production droplet, same approach as teardown)
echo -e "${YELLOW}Updating staging slot registry...${NC}"
PROD_ENV="${BASE_DIR}/.env.production"
if "${SSH_CMD[@]}" "${DROPLET_USER}@${PRODUCTION_DROPLET}" bash -s << REGISTRY_EOF
set -e
[[ -f "${PROD_ENV}" ]] || exit 1
set -a
source "${PROD_ENV}"
set +a
docker run --rm \\
  -e PGPASSWORD="\${POSTGRES_PASSWORD}" \\
  -e PGHOST="\${POSTGRES_HOST}" \\
  -e PGPORT="\${POSTGRES_PORT}" \\
  -e PGUSER="\${POSTGRES_USER}" \\
  -e PGDATABASE="\${POSTGRES_DB:-job_search_production}" \\
  -e PGSSLMODE=require \\
  postgres:15 \\
  psql -c "
  UPDATE marts.staging_slots
  SET status = 'In Use',
      owner = 'deploy',
      branch = '${BRANCH}',
      issue_id = '${DEPLOY_ISSUE_ID}',
      deployed_at = '$(date -u +%Y-%m-%dT%H:%M:%SZ)',
      purpose = 'QA: ${DEPLOY_ISSUE_ID} — Deployed via deploy-staging.sh',
      updated_at = CURRENT_TIMESTAMP
  WHERE slot_id = ${SLOT};
"
REGISTRY_EOF
then
  echo -e "  ${GREEN}✓ Staging slot ${SLOT} claimed in registry.${NC}"
else
  echo -e "  ${YELLOW}  Could not update registry (production env missing or psql failed).${NC}"
fi

echo ""
echo -e "${GREEN}=== ✓ Deployment successful ===${NC}"
echo "Staging slot ${SLOT} deployed:"
echo "  Branch: ${BRANCH}"
echo "  Commit: ${COMMIT_SHORT}"
echo "  Backend API: https://staging-${SLOT}.justapply.net"
echo "  Airflow UI:  https://staging-${SLOT}.justapply.net/airflow/"
echo ""
