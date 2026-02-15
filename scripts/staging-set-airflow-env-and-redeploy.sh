#!/bin/bash
# Set Airflow API env vars in .env.staging-N on the droplet and redeploy backend (and optionally full stack).
#
# Usage:
#   ./scripts/staging-set-airflow-env-and-redeploy.sh <slot> [full]
#
# Examples:
#   ./scripts/staging-set-airflow-env-and-redeploy.sh 4       # Slot 4: set env, recreate backend only
#   ./scripts/staging-set-airflow-env-and-redeploy.sh 4 full  # Slot 4: set env, full compose up -d
#
# Prerequisites: SSH access to staging droplet; .env.staging-N already exists.

set -euo pipefail

DROPLET_USER="deploy"
DROPLET_HOST="134.122.35.239"
BASE_DIR="/home/deploy"

SLOT=${1:-4}
FULL_DEPLOY=${2:-}

if [[ ! "$SLOT" =~ ^[1-9]$|^10$ ]]; then
    echo "Error: Slot must be between 1 and 10"
    exit 1
fi

SLOT_DIR="${BASE_DIR}/staging-${SLOT}"
PROJECT_DIR="${SLOT_DIR}/job-search-project"
ENV_FILE="${SLOT_DIR}/.env.staging-${SLOT}"

# Airflow API URL must use the staging container name (resolves on Docker network)
AIRFLOW_API_URL_VAL="http://staging-${SLOT}-airflow-webserver:8080/api/v1"
AIRFLOW_API_USER_VAL="admin"
AIRFLOW_API_PASS_VAL="staging${SLOT}admin"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh" ]]; then
    SSH_IDENTITY_FILE="${REPO_ROOT}/ssh-keys/digitalocean_laptop_ssh"
else
    SSH_IDENTITY_FILE=""
fi

SSH_CMD=(ssh)
[[ -n "${SSH_IDENTITY_FILE}" ]] && SSH_CMD+=(-i "${SSH_IDENTITY_FILE}")
SSH_CMD+=("${DROPLET_USER}@${DROPLET_HOST}" bash)

echo "=== Setting Airflow API env and redeploying staging-${SLOT} ==="

"${SSH_CMD[@]}" << REMOTE
set -euo pipefail

if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: ${ENV_FILE} not found. Create it first (e.g. with scripts/setup_staging_slot.sh)."
    exit 1
fi

# Remove existing AIRFLOW_API_* lines and append correct ones
sed -i.bak -e '/^AIRFLOW_API_URL=/d' -e '/^AIRFLOW_API_USERNAME=/d' -e '/^AIRFLOW_API_PASSWORD=/d' "${ENV_FILE}"
echo "" >> "${ENV_FILE}"
echo "# Airflow API (backend triggers DAGs)" >> "${ENV_FILE}"
echo "AIRFLOW_API_URL=${AIRFLOW_API_URL_VAL}" >> "${ENV_FILE}"
echo "AIRFLOW_API_USERNAME=${AIRFLOW_API_USER_VAL}" >> "${ENV_FILE}"
echo "AIRFLOW_API_PASSWORD=${AIRFLOW_API_PASS_VAL}" >> "${ENV_FILE}"
echo "Updated ${ENV_FILE} with AIRFLOW_API_*"

# Load env and export for compose
set -a
source "${ENV_FILE}"
set +a
export STAGING_SLOT=${SLOT}
export CAMPAIGN_UI_PORT=$((5000 + SLOT))
export AIRFLOW_WEBSERVER_PORT=$((8080 + SLOT))
export FRONTEND_PORT=$((5173 + SLOT))
export POSTGRES_NOOP_PORT=$((54000 + SLOT))

cd "${PROJECT_DIR}"
git fetch origin
git pull origin main || git pull origin master || true

if [ "${FULL_DEPLOY}" = "full" ]; then
    echo "=== Full compose up -d ==="
    docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" up -d
else
    echo "=== Recreating backend-api only ==="
    docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-${SLOT}" up -d --force-recreate backend-api
fi

echo "Done. Backend will use Airflow at ${AIRFLOW_API_URL_VAL}"
echo "UI: https://staging-${SLOT}.justapply.net  Airflow: https://staging-${SLOT}.justapply.net/airflow/"
REMOTE

echo ""
echo "Staging-${SLOT} backend updated. Try 'Start jobs' again and open Airflow at https://staging-${SLOT}.justapply.net/airflow/ (admin / staging${SLOT}admin)."
