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

# Optional: pass through to slot registry (per .cursorrules: branch, issue_id, purpose, deployed_at).
# Set ISSUE_ID and/or PURPOSE when deploying for QA so the slot shows PR/Linear link.
DEPLOY_ISSUE_ID="${ISSUE_ID:-$(echo "$BRANCH" | grep -oE 'JOB-[0-9]+' || echo '')}"
DEPLOY_PURPOSE="${PURPOSE:-QA: ${DEPLOY_ISSUE_ID} — Deployed via deploy-staging.sh}"
# Escape for embedding in Python double-quoted string (escape \ and ")
PY_PURPOSE=$(printf '%s' "$DEPLOY_PURPOSE" | sed 's/\\/\\\\/g; s/"/\\"/g')

if [[ -z "$SLOT" ]]; then
    echo -e "${RED}Error: Slot number is required${NC}"
    echo "Usage: $0 <slot_number> [branch]"
    echo "Optional env: ISSUE_ID, PURPOSE (for slot registry metadata)."
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

# Use project SSH key when present (so no ~/.ssh/config required)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "/Volumes/X9 Pro/Coding/Job Search Project/ssh-keys/digitalocean_laptop_ssh" ]]; then
  SSH_IDENTITY_FILE="/Volumes/X9 Pro/Coding/Job Search Project/ssh-keys/digitalocean_laptop_ssh"
elif [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
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
    git reset --hard
    git clean -fd || true
    git checkout -B "${BRANCH}" "origin/${BRANCH}"
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

# Copy slot env into project dir so docker compose finds .env.staging (avoids env_file not found)
# Remove destination first so we never copy onto a symlink (same file error)
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

# Export environment variables for docker compose (after sourcing env file to allow overrides)
export STAGING_SLOT=${SLOT}
export DEPLOYED_SHA="${COMMIT_SHA}"
export DEPLOYED_BRANCH="${BRANCH}"
export DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export CAMPAIGN_UI_PORT=${CAMPAIGN_UI_PORT}
export AIRFLOW_WEBSERVER_PORT=${AIRFLOW_PORT}
export FRONTEND_PORT=${FRONTEND_PORT}
export POSTGRES_NOOP_PORT=$((54000 + SLOT))

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
  bash -c 'cd /opt/airflow/dbt && dbt run --project-dir . --target-path /tmp/dbt_target --log-path /tmp/dbt_logs' || echo "WARNING: dbt run had errors; containers will still start."

echo "=== Ensuring Airflow logs dir is writable by container ==="
mkdir -p "${PROJECT_DIR}/airflow/logs"
chmod -R 777 "${PROJECT_DIR}/airflow/logs" || true

echo "=== Starting containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" up -d

echo "=== Verifying backend is up ==="
for i in 1 2 3 4 5; do
  if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${CAMPAIGN_UI_PORT}/api/health" | grep -q 200; then
    echo "Backend health OK (200)"
    break
  fi
  echo "Waiting for backend... (\$i/5)"
  sleep 3
done

echo "=== Seeding admin user (marts.users) ==="
# Ensure admin user exists so Staging Dashboard login works (admin / admin123).
# Uses one-off postgres client; staging uses managed DB (POSTGRES_* from env).
if [ -f "${PROJECT_DIR}/docker/init/19_seed_admin_user.sql" ]; then
  docker run --rm \
    -v "${PROJECT_DIR}/docker/init:/sql:ro" \
    -e PGPASSWORD="${POSTGRES_PASSWORD}" \
    -e PGHOST="${POSTGRES_HOST}" \
    -e PGPORT="${POSTGRES_PORT}" \
    -e PGUSER="${POSTGRES_USER}" \
    -e PGDATABASE="${POSTGRES_DB}" \
    -e PGSSLMODE=require \
    postgres:15 \
    psql -f /sql/19_seed_admin_user.sql \
  && echo "Admin user seeded." || echo "WARNING: Admin seed failed (login may not work until fixed)."
else
  echo "WARNING: 19_seed_admin_user.sql not found; skipping admin seed."
fi

echo "=== Updating nginx config for staging (if sudo available) ==="
# Multi-slot droplets: copy config and enable it so staging-N.justapply.net works
if [ -f "${PROJECT_DIR}/infra/nginx/staging-multi.conf" ]; then
  sudo cp -f "${PROJECT_DIR}/infra/nginx/staging-multi.conf" /etc/nginx/sites-available/staging-multi
  sudo ln -sf /etc/nginx/sites-available/staging-multi /etc/nginx/sites-enabled/staging-multi
fi
# Fallback: single staging config
if [ -f "${PROJECT_DIR}/infra/nginx/staging-justapply.conf" ]; then
  sudo cp -f "${PROJECT_DIR}/infra/nginx/staging-justapply.conf" /etc/nginx/sites-available/staging-justapply.conf
  sudo ln -sf /etc/nginx/sites-available/staging-justapply.conf /etc/nginx/sites-enabled/staging-justapply.conf
fi
sudo nginx -t && sudo systemctl reload nginx || echo "Skipped (copy nginx config and reload manually if needed)."

echo "=== Waiting for services to be healthy ==="
sleep 10

# Check service health
echo "=== Checking service health ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" ps

echo ""
echo "=== Deployment complete ==="
echo "Backend API: https://staging-\${SLOT}.justapply.net"
echo "Airflow UI:  https://staging-\${SLOT}.justapply.net/airflow/"
echo ""

# Update staging slot registry in database
echo "=== Updating staging slot registry in database ==="
# Run a small python script to update the marts.staging_slots table
# We use the environment variables already set in the shell
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" exec -T airflow-webserver python3 -c "
import os
import psycopg2
from datetime import datetime

try:
    conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT'), user=os.getenv('POSTGRES_USER'), password=os.getenv('POSTGRES_PASSWORD'), dbname=os.getenv('POSTGRES_DB'), sslmode='require')
    with conn.cursor() as cur:
        cur.execute(\"\"\"
            UPDATE marts.staging_slots
            SET status = 'In Use',
                owner = %s,
                branch = %s,
                issue_id = %s,
                deployed_at = %s,
                purpose = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE slot_id = %s
        \"\"\", (
            os.getenv('USER', 'unknown'),
            '${BRANCH}',
            '${DEPLOY_ISSUE_ID}',
            datetime.now(),
            """${PY_PURPOSE}""",
            ${SLOT}
        ))
    conn.commit()
    conn.close()
    print('Successfully updated staging_slots table')
except Exception as e:
    print(f'Failed to update staging_slots table: {e}')
" || true

EOF

echo -e "${GREEN}=== Deployment successful ===${NC}"
echo ""
echo "Staging slot ${SLOT} deployed:"
echo "  Branch: ${BRANCH}"
echo "  Commit: ${COMMIT_SHORT}"
echo "  Backend API: http://${DROPLET_HOST}:${CAMPAIGN_UI_PORT}"
echo "  Airflow UI:  http://${DROPLET_HOST}:${AIRFLOW_PORT}"
echo ""
echo "Slot registry is in the database (marts.staging_slots); no file update required."
