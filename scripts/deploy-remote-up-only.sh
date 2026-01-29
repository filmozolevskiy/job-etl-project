#!/bin/bash
set -e
cd /home/deploy/staging-10/job-search-project
ln -sf ../.env.staging-10 .env
ln -sf ../.env.staging-10 .env.staging
export STAGING_SLOT=10
export AIRFLOW_WEBSERVER_PORT=8090
export CAMPAIGN_UI_PORT=5010
export FRONTEND_PORT=5183
export ENVIRONMENT=staging
set -a
source /home/deploy/staging-10/.env.staging-10
set +a
export DEPLOYED_SHA=$(git rev-parse HEAD 2>/dev/null || true)
export DEPLOYED_BRANCH=main

echo "=== Removing orphan run containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 down --remove-orphans 2>/dev/null || true

echo "=== Starting containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 up -d

echo "=== Waiting for services ==="
sleep 30
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 ps -a
