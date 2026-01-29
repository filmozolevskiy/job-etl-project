#!/bin/bash
# Check why normalize_jobs is failing

source ~/staging-10/.env.staging-10

echo "=== Checking raw.jsearch_job_postings count ==="
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT COUNT(*) as count FROM raw.jsearch_job_postings;"

echo ""
echo "=== Testing dbt run manually ==="
cd /home/deploy/staging-10/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "cd /opt/airflow/dbt && dbt run --select staging.jsearch_job_postings --profiles-dir . 2>&1" | tail -100
