#!/bin/bash
# Get task log content from Airflow

SLOT="${1:-10}"
TASK_ID="${2:-normalize_jobs}"

cd /home/deploy/staging-${SLOT}/job-search-project

echo "=== Finding latest log file for ${TASK_ID} ==="
LOG_DIR="/opt/airflow/logs/dag_id=jobs_etl_daily"

# List all task directories
TASK_DIRS=$(docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "ls -1td '${LOG_DIR}'/run_id=*/${TASK_ID} 2>/dev/null | head -3" | tr -d '\r')

if [ -z "$TASK_DIRS" ]; then
  echo "No task directories found"
  echo "Available DAG runs:"
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "ls -1td '${LOG_DIR}'/run_id=* 2>/dev/null | head -5"
  exit 1
fi

echo "Found task directories:"
echo "$TASK_DIRS"
echo ""

# Get the most recent log file
for TASK_DIR in $TASK_DIRS; do
  echo "=== Checking ${TASK_DIR} ==="
  LOG_FILE=$(docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "ls -1t '${TASK_DIR}'/*.log 2>/dev/null | head -1" | tr -d '\r\n')
  
  if [ -n "$LOG_FILE" ]; then
    echo "Log file: $LOG_FILE"
    echo ""
    echo "=== Log content (last 500 lines) ==="
    docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "tail -500 '$LOG_FILE' 2>/dev/null"
    echo ""
    echo "=== End of log ==="
    break
  fi
done
