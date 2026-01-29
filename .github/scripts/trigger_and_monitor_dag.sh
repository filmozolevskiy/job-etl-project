#!/bin/bash
# Trigger a DAG run and monitor until completion
# Usage: ./trigger_and_monitor_dag.sh <dag_id>

set -euo pipefail

DAG_ID="${1:-jobs_etl_daily}"
source ~/staging-10/.env.staging-10

AIRFLOW_URL="http://localhost:8090/api/v1"
AUTH="${AIRFLOW_USERNAME}:${AIRFLOW_PASSWORD}"

echo "=== Triggering DAG: ${DAG_ID} ==="
TRIGGER_RESPONSE=$(curl -s -u "${AUTH}" -X POST \
  "${AIRFLOW_URL}/dags/${DAG_ID}/dagRuns" \
  -H "Content-Type: application/json" \
  -d '{"dag_run_id": "manual_'$(date +%s)'"}')

echo "$TRIGGER_RESPONSE" | python3 -m json.tool || echo "$TRIGGER_RESPONSE"
DAG_RUN_ID=$(echo "$TRIGGER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('dag_run_id', ''))" 2>/dev/null || echo "")

if [ -z "$DAG_RUN_ID" ]; then
  echo "ERROR: Failed to trigger DAG or extract run_id"
  exit 1
fi

echo ""
echo "DAG Run ID: ${DAG_RUN_ID}"
echo "Monitoring execution..."

# Monitor until completion (max 30 minutes)
MAX_ITERATIONS=180
ITERATION=0
while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  sleep 10
  ITERATION=$((ITERATION + 1))
  
  # Get DAG run status
  STATUS_RESPONSE=$(curl -s -u "${AUTH}" -X GET \
    "${AIRFLOW_URL}/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}")
  
  STATE=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('state', 'unknown'))" 2>/dev/null || echo "unknown")
  
  if [ "$((ITERATION % 6))" -eq 0 ]; then
    echo "[$((ITERATION * 10))s] DAG Run State: ${STATE}"
  fi
  
  # Check if completed (success or failed)
  if [ "$STATE" = "success" ]; then
    echo ""
    echo "✅ DAG completed successfully!"
    
    # Get task instances
    TASKS_RESPONSE=$(curl -s -u "${AUTH}" -X GET \
      "${AIRFLOW_URL}/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}/taskInstances")
    
    echo ""
    echo "=== Task Status Summary ==="
    echo "$TASKS_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tasks = data.get('task_instances', [])
for task in tasks:
    state = task.get('state', 'unknown')
    task_id = task.get('task_id', 'unknown')
    print(f'{task_id}: {state}')
" 2>/dev/null || echo "Could not parse task status"
    
    # Check for any failed tasks
    FAILED_COUNT=$(echo "$TASKS_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tasks = data.get('task_instances', [])
failed = [t for t in tasks if t.get('state') == 'failed']
print(len(failed))
" 2>/dev/null || echo "0")
    
    if [ "$FAILED_COUNT" -gt 0 ]; then
      echo ""
      echo "⚠️  WARNING: ${FAILED_COUNT} task(s) failed!"
      exit 1
    else
      echo ""
      echo "✅ All tasks completed successfully!"
      exit 0
    fi
  elif [ "$STATE" = "failed" ]; then
    echo ""
    echo "❌ DAG run failed!"
    exit 1
  fi
done

echo ""
echo "⏱️  Timeout: DAG run did not complete within 30 minutes"
exit 1
