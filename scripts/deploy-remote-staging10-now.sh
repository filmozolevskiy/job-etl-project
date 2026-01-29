#!/bin/bash
set -euo pipefail
SLOT=10
BASE=/home/deploy
SLOT_DIR=$BASE/staging-$SLOT
PROJECT_DIR=$SLOT_DIR/job-search-project
ENV_FILE=$SLOT_DIR/.env.staging-$SLOT

echo "=== Deploy staging-10 ==="
mkdir -p "$SLOT_DIR"
cd "$PROJECT_DIR"

echo "=== Git pull ==="
git fetch origin
git checkout main
git pull origin main

echo "=== Env and compose config ==="
export STAGING_SLOT=$SLOT
export AIRFLOW_WEBSERVER_PORT=8090
export CAMPAIGN_UI_PORT=5010
export FRONTEND_PORT=5183
set -a
source "$ENV_FILE"
set +a
export DEPLOYED_SHA=$(git rev-parse HEAD)
export DEPLOYED_BRANCH=main

echo "=== Down ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 down --remove-orphans || true

echo "=== Build ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 build

echo "=== Initial dbt (writable paths) ==="
cp -f dbt/profiles.staging.yml dbt/profiles.yml
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 run --rm --no-deps airflow-webserver \
  bash -c 'cd /opt/airflow/dbt && dbt run --project-dir . --target-path /tmp/dbt_target --log-path /tmp/dbt_logs'

echo "=== Up -d ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 up -d

echo "=== Wait 15s ==="
sleep 15
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 ps

echo "=== Deploy done ==="
