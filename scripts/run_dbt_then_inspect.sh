#!/bin/bash
set -e
cd /home/deploy/staging-10/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c '
cd /opt/airflow/dbt
dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt || true
echo "=== pwd ls ==="
ls -la
echo "=== target ==="
ls -la target/ 2>/dev/null || true
echo "=== logs ==="
ls -la logs/ 2>/dev/null || true
echo "=== logs/dbt.log ==="
cat logs/dbt.log 2>/dev/null || true
echo "=== root logs ==="
ls -la /opt/airflow/logs/
'
