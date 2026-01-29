#!/bin/bash
source /home/deploy/staging-10/.env.staging-10
RUN_ID="${1:?usage: monitor_dag_run.sh <dag_run_id>}"
AIRFLOW_URL="http://localhost:8090/api/v1"
AUTH="${AIRFLOW_USERNAME}:${AIRFLOW_PASSWORD}"
MAX=120
n=0
while [ $n -lt $MAX ]; do
  s=$(curl -s -u "${AUTH}" "${AIRFLOW_URL}/dags/jobs_etl_daily/dagRuns/${RUN_ID}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('state','?'))" 2>/dev/null || echo "?")
  echo "[$((n*10))s] state=$s"
  [ "$s" = "success" ] && echo "DAG succeeded!" && exit 0
  [ "$s" = "failed" ] && echo "DAG failed!" && exit 1
  sleep 10
  n=$((n+1))
done
echo "Timeout"
exit 1