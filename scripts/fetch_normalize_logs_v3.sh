#!/bin/bash
set -e
cd /home/deploy/staging-10/job-search-project
echo "=== Airflow logs root ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler ls -la /opt/airflow/logs 2>/dev/null || true
echo ""
echo "=== dag_id=jobs_etl_daily run dirs ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler ls -la /opt/airflow/logs/dag_id=jobs_etl_daily
echo ""
echo "=== run_id=manual_1769643205 contents ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler ls -la "/opt/airflow/logs/dag_id=jobs_etl_daily/run_id=manual_1769643205" 2>/dev/null || true
echo ""
echo "=== normalize_jobs task dir ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler ls -la "/opt/airflow/logs/dag_id=jobs_etl_daily/run_id=manual_1769643205/task_id=normalize_jobs" 2>/dev/null || true
echo ""
echo "=== Tail normalize_jobs log ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "tail -400 /opt/airflow/logs/dag_id=jobs_etl_daily/run_id=manual_1769643205/task_id=normalize_jobs/*.log 2>/dev/null" || true
