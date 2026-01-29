#!/usr/bin/env python3
"""Get detailed task logs from Airflow API."""

import sys

import requests
from requests.auth import HTTPBasicAuth

DAG_ID = sys.argv[1] if len(sys.argv) > 1 else "jobs_etl_daily"
TASK_ID = sys.argv[2] if len(sys.argv) > 2 else "normalize_jobs"
DAG_RUN_ID = sys.argv[3] if len(sys.argv) > 3 else None
TRY_NUM = int(sys.argv[4]) if len(sys.argv) > 4 else 1

AUTH = HTTPBasicAuth("admin", "staging10admin")
BASE_URL = "http://localhost:8090/api/v1"

if not DAG_RUN_ID:
    # Get latest DAG run
    r = requests.get(f"{BASE_URL}/dags/{DAG_ID}/dagRuns?limit=1", auth=AUTH)
    dag_runs = r.json().get("dag_runs", [])
    if not dag_runs:
        print("No DAG runs found")
        sys.exit(1)
    DAG_RUN_ID = dag_runs[0]["dag_run_id"]
    print(f"Using latest DAG run: {DAG_RUN_ID}")

# Get task instance
r = requests.get(
    f"{BASE_URL}/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}/taskInstances/{TASK_ID}",
    auth=AUTH,
)
task = r.json()
print(f"Task State: {task.get('state')}")
print(f"Try Number: {task.get('try_number')}")
print()

# Try to get logs for each try
for try_num in range(1, task.get("try_number", 1) + 1):
    r2 = requests.get(
        f"{BASE_URL}/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}/taskInstances/{TASK_ID}/logs/{try_num}",
        auth=AUTH,
    )
    if r2.status_code == 200:
        logs = r2.json()
        content = logs.get("content", "")
        if content and content.strip():
            print(f"=== Logs (Try {try_num}) ===")
            print(content)
            print()
            break
    elif r2.status_code == 404:
        continue
    else:
        print(f"Failed to get logs for try {try_num}: {r2.status_code}")
        print(r2.text[:500])
