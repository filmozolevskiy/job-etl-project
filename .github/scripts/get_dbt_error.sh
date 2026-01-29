#!/bin/bash
# Get dbt error from latest normalize_jobs task

DAG_RUN_ID="${1:-debug_dbt_error_1769605366}"

cd /home/deploy/staging-10/job-search-project

LOG_FILE=$(docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "ls -t /opt/airflow/logs/dag_id=jobs_etl_daily/run_id=${DAG_RUN_ID}/task_id=normalize_jobs/*.log 2>/dev/null | head -1" | tr -d '\r\n')

if [ -n "$LOG_FILE" ]; then
  echo "=== Log file: $LOG_FILE ==="
  echo ""
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "cat '$LOG_FILE' | tail -300"
else
  echo "Log file not found for ${DAG_RUN_ID}"
  echo "Available runs:"
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "ls -1td /opt/airflow/logs/dag_id=jobs_etl_daily/run_id=* 2>/dev/null | head -5"
fi
