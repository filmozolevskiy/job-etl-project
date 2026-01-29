#!/bin/bash
set -e
cd /home/deploy/staging-10/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c '
cd /opt/airflow/dbt
dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt || true
echo "=== logs dir ==="
ls -la logs/ 2>/dev/null || true
echo "=== dbt.log tail ==="
tail -100 logs/dbt.log 2>/dev/null || true
echo "=== /tmp dbt log ==="
cat /tmp/dbt_normalize_jobs.log 2>/dev/null || true
'
