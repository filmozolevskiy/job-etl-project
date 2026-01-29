#!/bin/bash
# Check Airflow task logs from filesystem

SLOT="${1:-10}"
TASK_ID="${2:-normalize_jobs}"
DAG_RUN_ID="${3:-manual_fixed_v2_1769517584}"

cd /home/deploy/staging-${SLOT}/job-search-project

echo "=== Checking logs directory ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "ls -la /opt/airflow/logs/ 2>/dev/null | head -10"

echo ""
echo "=== Finding task log files ==="
LOG_FILE=$(docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "find /opt/airflow/logs -name '*${TASK_ID}*' -type f 2>/dev/null | grep -i '${DAG_RUN_ID}' | head -1" | tr -d '\r')

if [ -n "$LOG_FILE" ]; then
  echo "Found log file: $LOG_FILE"
  echo ""
  echo "=== Log contents (last 300 lines) ==="
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "cat '$LOG_FILE' 2>/dev/null | tail -300"
else
  echo "No log file found for ${TASK_ID} in ${DAG_RUN_ID}"
  echo ""
  echo "=== Available log directories ==="
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-${SLOT} exec -T airflow-scheduler bash -c "find /opt/airflow/logs -type d -name '*${TASK_ID}*' 2>/dev/null | head -5"
fi
