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
export DEPLOYED_SHA=$(git -C /home/deploy/staging-10/job-search-project rev-parse HEAD 2>/dev/null || true)
export DEPLOYED_BRANCH=main
cp -f dbt/profiles.staging.yml dbt/profiles.yml
echo "=== Running dbt ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 run --rm --no-deps airflow-webserver bash -c 'cd /opt/airflow/dbt && dbt run --project-dir .' 2>&1 | tee /tmp/dbt-run.log
rc=${PIPESTATUS[0]}
echo "dbt exit code: $rc"
[ "$rc" -ne 0 ] && (echo "dbt failed. Log:"; cat /tmp/dbt-run.log) && exit "$rc"
echo "=== Starting containers ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 up -d
sleep 25
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 ps -a
