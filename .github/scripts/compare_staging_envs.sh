#!/bin/bash
# Compare staging-1 and staging-10 configurations

echo "=== Environment Variables ==="
echo ""
echo "Staging-1 POSTGRES_*:"
grep "^POSTGRES_" ~/staging-1/.env.staging-1 | sort
echo ""
echo "Staging-10 POSTGRES_*:"
grep "^POSTGRES_" ~/staging-10/.env.staging-10 | sort

echo ""
echo "=== Database Schemas ==="
echo ""
echo "Staging-1 schemas:"
source ~/staging-1/.env.staging-1
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('dbt', 'raw', 'staging', 'marts') ORDER BY schema_name;"

echo ""
echo "Staging-10 schemas:"
source ~/staging-10/.env.staging-10
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('dbt', 'raw', 'staging', 'marts') ORDER BY schema_name;"

echo ""
echo "=== Container Environment (Staging-10) ==="
cd ~/staging-10/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c 'env | grep -E "POSTGRES_|ENVIRONMENT" | sort' || echo "Container not running"

echo ""
echo "=== Testing dbt connection (Staging-10) ==="
cd ~/staging-10/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c 'cd /opt/airflow/dbt && timeout 10 dbt debug --profiles-dir . --profile job_search_platform --target staging 2>&1' | tail -20 || echo "dbt debug failed or timed out"
