#!/bin/bash
set -e
cd /home/deploy/staging-10/job-search-project
BASE="/opt/airflow/logs/dag_id=jobs_etl_daily"
echo "=== Latest run_id dirs ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler ls -1td "${BASE}"/run_id=* 2>/dev/null | head -5
echo ""
echo "=== normalize_jobs log (latest run) ==="
RUN_DIR=$(docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "ls -1td ${BASE}/run_id=* 2>/dev/null | head -1" | tr -d '\r\n')
echo "Run dir: $RUN_DIR"
TASK_DIR="${RUN_DIR}/task_id=normalize_jobs"
echo "Listing $TASK_DIR:"
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler ls -la "$TASK_DIR" 2>/dev/null || true
echo ""
LOG=$(docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "ls -1t ${TASK_DIR}/*.log 2>/dev/null | head -1" | tr -d '\r\n')
[ -n "$LOG" ] && echo "Tail of $LOG:" && docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler tail -300 "$LOG" 2>/dev/null || true
