#!/bin/bash
source /home/deploy/staging-10/.env.staging-10
RUN_ID="${1:-manual_1769643205}"
curl -s -u "${AIRFLOW_USERNAME}:${AIRFLOW_PASSWORD}" \
  "http://localhost:8090/api/v1/dags/jobs_etl_daily/dagRuns/${RUN_ID}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('State:', d.get('state')); print('End:', d.get('end_date'))"
