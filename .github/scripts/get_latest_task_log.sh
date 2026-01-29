#!/bin/bash
# Get the latest task log file

SLOT="${1:-10}"
TASK_ID="${2:-normalize_jobs}"

cd /home/deploy/staging-${SLOT}/job-search-project

# Find the most recent log file
LOG_FILE=$(docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "find /opt/airflow/logs -name '*${TASK_ID}*' -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-" | tr -d '\r\n')

if [ -n "$LOG_FILE" ]; then
  echo "=== Log file: $LOG_FILE ==="
  echo ""
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "tail -300 '$LOG_FILE' 2>/dev/null"
else
  echo "No log file found"
  echo "Listing available log directories:"
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "ls -la /opt/airflow/logs/dag_id=jobs_etl_daily/ 2>/dev/null | head -20"
fi
