#!/bin/bash
# Run on droplet: get latest DAG run + normalize_jobs logs
set -e
source /home/deploy/staging-10/.env.staging-10
AIRFLOW_URL="http://localhost:8090/api/v1"
AUTH="${AIRFLOW_USERNAME}:${AIRFLOW_PASSWORD}"

# Latest run
RUNS=$(curl -s -u "${AUTH}" "${AIRFLOW_URL}/dags/jobs_etl_daily/dagRuns?limit=3&order_by=-start_date")
echo "$RUNS" | python3 -c "
import sys, json
r = json.load(sys.stdin)
for x in r.get('dag_runs', []):
    print(x.get('dag_run_id'), x.get('state'), x.get('start_date'))
"

# Get latest run id
RUN_ID=$(echo "$RUNS" | python3 -c "import sys,json; r=json.load(sys.stdin); runs=r.get('dag_runs',[]); print(runs[0]['dag_run_id'] if runs else '')")
[ -z "$RUN_ID" ] && echo "No DAG runs" && exit 1

echo ""
echo "=== normalize_jobs for run $RUN_ID ==="
curl -s -u "${AUTH}" "${AIRFLOW_URL}/dags/jobs_etl_daily/dagRuns/${RUN_ID}/taskInstances" | python3 -c "
import sys, json
r = json.load(sys.stdin)
for t in r.get('task_instances', []):
    if t.get('task_id') == 'normalize_jobs':
        print('state:', t.get('state'), 'try:', t.get('try_number'))
        break
"

echo ""
echo "=== Logs (try 1) ==="
LOG=$(curl -s -u "${AUTH}" "${AIRFLOW_URL}/dags/jobs_etl_daily/dagRuns/${RUN_ID}/taskInstances/normalize_jobs/logs/1")
echo "$LOG" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('content', '')[:8000])
except Exception as e:
    print('Parse error:', e)
    print(sys.stdin.read()[:2000])
" 2>/dev/null || echo "$LOG" | head -c 8000
