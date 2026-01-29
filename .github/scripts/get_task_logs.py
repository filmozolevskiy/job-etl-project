#!/usr/bin/env python3
"""Get task logs from Airflow."""

import sys

import requests
from requests.auth import HTTPBasicAuth

DAG_ID = sys.argv[1] if len(sys.argv) > 1 else "jobs_etl_daily"
DAG_RUN_ID = sys.argv[2] if len(sys.argv) > 2 else None
TASK_ID = sys.argv[3] if len(sys.argv) > 3 else None

if not DAG_RUN_ID or not TASK_ID:
    print("Usage: python3 get_task_logs.py <dag_id> <dag_run_id> <task_id>")
    sys.exit(1)

AIRFLOW_URL = "http://localhost:8090/api/v1"
AUTH = HTTPBasicAuth("admin", "staging10admin")

# Get logs for the task
response = requests.get(
    f"{AIRFLOW_URL}/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}/taskInstances/{TASK_ID}/logs/1",
    auth=AUTH
)

logs = response.json()
print("=== Task Logs ===")
print(logs.get("content", "No logs found"))
