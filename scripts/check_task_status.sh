#!/bin/bash
# Check task status for the latest DAG run
DAG_RUN_ID="${1:-manual__2026-01-22T15:10:06.132201+00:00}"
curl -s -u admin:staging1admin "http://localhost:8081/api/v1/dags/jobs_etl_daily/dagRuns/${DAG_RUN_ID}/taskInstances" | \
  python3 << 'PYEOF'
import sys, json
data = json.load(sys.stdin)
for t in data["task_instances"]:
    task_id = t["task_id"]
    state = t["state"]
    try_num = t["try_number"]
    print(f"{task_id}: {state} (try:{try_num})")
PYEOF
