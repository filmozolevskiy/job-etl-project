#!/bin/bash
set -euo pipefail
SLOT=10
BRANCH=main
BASE_DIR=/home/deploy
SLOT_DIR="${BASE_DIR}/staging-${SLOT}"
PROJECT_DIR="${SLOT_DIR}/job-search-project"
ENV_FILE="${SLOT_DIR}/.env.staging-${SLOT}"
REPO_URL="git@github.com:filmozolevskiy/job-etl-project.git"
CAMPAIGN_UI_PORT=$((5000 + SLOT))
AIRFLOW_PORT=$((8080 + SLOT))
FRONTEND_PORT=$((5173 + SLOT))
DROPLET_HOST="134.122.35.239"

echo "=== Preparing slot directory ==="
mkdir -p "${SLOT_DIR}"
cd "${SLOT_DIR}"

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

COMMIT_SHA=$(git rev-parse HEAD)
COMMIT_SHORT=$(git rev-parse --short HEAD)

if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: Environment file not found: ${ENV_FILE}"
    exit 1
fi

echo "=== Writing deployment metadata ==="
cat > "${SLOT_DIR}/version.json" << VERSIONEOF
{
    "slot": ${SLOT},
    "branch": "${BRANCH}",
    "commit_sha": "${COMMIT_SHA}",
    "commit_short": "${COMMIT_SHORT}",
    "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "deployed_by": "remote-deploy"
}
VERSIONEOF

export STAGING_SLOT=${SLOT}
export DEPLOYED_SHA="${COMMIT_SHA}"
export DEPLOYED_BRANCH="${BRANCH}"
export CAMPAIGN_UI_PORT=${CAMPAIGN_UI_PORT}
export AIRFLOW_WEBSERVER_PORT=${AIRFLOW_PORT}
export FRONTEND_PORT=${FRONTEND_PORT}
export ENVIRONMENT=staging

set -a
source "${ENV_FILE}"
set +a

# Symlink env for compose (like workflow)
cd "${PROJECT_DIR}"
ln -sf "../.env.staging-${SLOT}" .env
ln -sf "../.env.staging-${SLOT}" .env.staging

echo "=== Stopping existing containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" down --remove-orphans || true

echo "=== Building containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" build

echo "=== Running initial dbt (create marts including fact_jobs) ==="
cp -f dbt/profiles.staging.yml dbt/profiles.yml
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" run --rm --no-deps airflow-webserver \
  bash -c 'cd /opt/airflow/dbt && dbt run --project-dir .'

echo "=== Starting containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" up -d

echo "=== Waiting for services ==="
sleep 15
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" ps -a
echo ""
echo "=== Deployment complete ==="
echo "Campaign UI: http://${DROPLET_HOST}:${CAMPAIGN_UI_PORT}"
echo "Airflow UI:  http://${DROPLET_HOST}:${AIRFLOW_PORT}"
echo "Commit: ${COMMIT_SHORT}"
