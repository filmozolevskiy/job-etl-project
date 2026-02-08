#!/bin/bash
set -euo pipefail
source /home/deploy/staging-10/.env.staging-10
DAG_ID="${1:-jobs_etl_daily}"
AIRFLOW_URL="http://localhost:8090/api/v1"
AUTH="${AIRFLOW_USERNAME}:${AIRFLOW_PASSWORD}"

echo "=== Triggering DAG: ${DAG_ID} ==="
TRIGGER_RESPONSE=$(curl -s -u "${AUTH}" -X POST \
  "${AIRFLOW_URL}/dags/${DAG_ID}/dagRuns" \
  -H "Content-Type: application/json" \
  -d "{\"dag_run_id\": \"manual_$(date +%s)\"}")

echo "$TRIGGER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TRIGGER_RESPONSE"
DAG_RUN_ID=$(echo "$TRIGGER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('dag_run_id', ''))" 2>/dev/null || echo "")

if [ -z "$DAG_RUN_ID" ]; then
  echo "ERROR: Failed to trigger DAG or extract run_id"
  exit 1
fi

echo ""
echo "DAG Run ID: ${DAG_RUN_ID}"
echo "Monitoring execution..."

MAX_ITERATIONS=180
ITERATION=0
while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  sleep 10
  ITERATION=$((ITERATION + 1))
  STATUS_RESPONSE=$(curl -s -u "${AUTH}" -X GET \
    "${AIRFLOW_URL}/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}")
  STATE=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('state', 'unknown'))" 2>/dev/null || echo "unknown")

  if [ "$((ITERATION % 6))" -eq 0 ]; then
    echo "[$((ITERATION * 10))s] DAG Run State: ${STATE}"
  fi

  if [ "$STATE" = "success" ]; then
    echo ""
    echo "DAG completed successfully!"
    TASKS_RESPONSE=$(curl -s -u "${AUTH}" -X GET \
      "${AIRFLOW_URL}/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}/taskInstances")
    echo "$TASKS_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tasks = data.get('task_instances', [])
for t in sorted(tasks, key=lambda x: x.get('task_id','')): print('  ', t.get('task_id'), ':', t.get('state'))
sys.exit(len([t for t in tasks if t.get('state') == 'failed']))
" 2>/dev/null || true
    [ $? -ne 0 ] && echo "Some tasks failed!" && exit 1
    echo ""
    echo "All tasks completed successfully!"
    exit 0
  elif [ "$STATE" = "failed" ]; then
    echo ""
    echo "DAG run failed!"
    exit 1
  fi
done

echo "Timeout: DAG did not complete within 30 minutes"
exit 1
