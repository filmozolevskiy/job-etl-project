#!/usr/bin/env python3
"""Check DAG run status and task states."""

import sys

import requests
from requests.auth import HTTPBasicAuth

DAG_ID = sys.argv[1] if len(sys.argv) > 1 else "jobs_etl_daily"
DAG_RUN_ID = sys.argv[2] if len(sys.argv) > 2 else None

AIRFLOW_URL = "http://localhost:8090/api/v1"
AUTH = HTTPBasicAuth("admin", "staging10admin")

if DAG_RUN_ID:
    # Check specific DAG run
    response = requests.get(f"{AIRFLOW_URL}/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}", auth=AUTH)
    dag_run = response.json()
    print(f"DAG Run: {DAG_RUN_ID}")
    print(f"State: {dag_run.get('state')}")
    print(f"Start: {dag_run.get('start_date')}")
    print(f"End: {dag_run.get('end_date')}")
    print()

    # Get task instances
    tasks_response = requests.get(
        f"{AIRFLOW_URL}/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}/taskInstances", auth=AUTH
    )
    tasks = tasks_response.json().get("task_instances", [])

    print("Task Status:")
    for task in sorted(tasks, key=lambda x: x.get("task_id", "")):
        task_id = task.get("task_id", "unknown")
        state = task.get("state", "no_state")
        print(f"  {task_id}: {state}")

    # Count states
    states = {}
    for task in tasks:
        state = task.get("state") or "no_state"
        states[state] = states.get(state, 0) + 1

    print()
    print("Summary:")
    for state, count in sorted(states.items()):
        print(f"  {state}: {count}")

    # Exit code based on final state
    if dag_run.get("state") == "success":
        failed = states.get("failed", 0)
        if failed > 0:
            print(f"\n⚠️  WARNING: {failed} task(s) failed!")
            sys.exit(1)
        else:
            print("\n✅ All tasks completed successfully!")
            sys.exit(0)
    elif dag_run.get("state") == "failed":
        print("\n❌ DAG run failed!")
        sys.exit(1)
    else:
        print(f"\n⏳ DAG run is {dag_run.get('state')}")
        sys.exit(2)
else:
    # List recent DAG runs
    response = requests.get(f"{AIRFLOW_URL}/dags/{DAG_ID}/dagRuns", auth=AUTH, params={"limit": 5})
    runs = response.json().get("dag_runs", [])

    print(f"Recent runs for DAG: {DAG_ID}")
    for run in runs:
        print(f"  {run.get('dag_run_id')}: {run.get('state')}")
