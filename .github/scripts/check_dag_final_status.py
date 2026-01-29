#!/usr/bin/env python3
"""Check final DAG run status."""

import sys

import requests
from requests.auth import HTTPBasicAuth

DAG_ID = sys.argv[1] if len(sys.argv) > 1 else "jobs_etl_daily"
DAG_RUN_ID = sys.argv[2] if len(sys.argv) > 2 else None

if not DAG_RUN_ID:
    print("Usage: python3 check_dag_final_status.py <dag_id> <dag_run_id>")
    sys.exit(1)

AIRFLOW_URL = "http://localhost:8090/api/v1"
AUTH = HTTPBasicAuth("admin", "staging10admin")

# Get DAG run status
response = requests.get(
    f"{AIRFLOW_URL}/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}",
    auth=AUTH
)
dag_run = response.json()
print(f"DAG State: {dag_run.get('state')}")
print(f"Start: {dag_run.get('start_date')}")
print(f"End: {dag_run.get('end_date')}")
print()

# Get task instances
tasks_response = requests.get(
    f"{AIRFLOW_URL}/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}/taskInstances",
    auth=AUTH
)
tasks = tasks_response.json().get('task_instances', [])

print("Task States:")
states_summary = {}
for task in sorted(tasks, key=lambda x: x.get('task_id', '')):
    task_id = task.get('task_id', 'unknown')
    state = task.get('state') or 'no_state'
    try_num = task.get('try_number', 0)
    max_tries = task.get('max_tries', 0)
    states_summary[state] = states_summary.get(state, 0) + 1
    print(f"  {task_id}: {state} (try {try_num}/{max_tries})")

print()
print("Summary:")
for state, count in sorted(states_summary.items()):
    print(f"  {state}: {count}")

# Final verdict
dag_state = dag_run.get('state')
if dag_state == 'success':
    failed = states_summary.get('failed', 0)
    if failed == 0:
        print("\n✅ All tasks completed successfully!")
        sys.exit(0)
    else:
        print(f"\n⚠️  WARNING: {failed} task(s) failed!")
        sys.exit(1)
elif dag_state == 'failed':
    print("\n❌ DAG run failed!")
    sys.exit(1)
else:
    print(f"\n⏳ DAG run is {dag_state}")
    sys.exit(2)
