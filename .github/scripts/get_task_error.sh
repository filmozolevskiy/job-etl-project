#!/bin/bash
# Get detailed error for a specific task

DAG_ID="${1:-jobs_etl_daily}"
TASK_ID="${2:-normalize_jobs}"
DAG_RUN_ID="${3:-manual_after_fix_1769516910}"
TRY_NUM="${4:-1}"

python3 << PYEOF
import requests
from requests.auth import HTTPBasicAuth

AUTH = HTTPBasicAuth('admin', 'staging10admin')

# Get task instance details
r = requests.get(
    f'http://localhost:8090/api/v1/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}/taskInstances/{TASK_ID}',
    auth=AUTH
)
task = r.json()
print('Task State:', task.get('state'))
print('Try Number:', task.get('try_number'))
print('Start Date:', task.get('start_date'))
print('End Date:', task.get('end_date'))
print('Duration:', task.get('duration'))
print()

# Try to get logs
for try_num in [1, 2, 3]:
    r2 = requests.get(
        f'http://localhost:8090/api/v1/dags/{DAG_ID}/dagRuns/{DAG_RUN_ID}/taskInstances/{TASK_ID}/logs/{try_num}',
        auth=AUTH
    )
    if r2.status_code == 200:
        logs = r2.json()
        content = logs.get('content', '')
        if content and content.strip():
            print(f'=== Logs (Try {try_num}) ===')
            print(content[:2000])
            print()
            break
    elif r2.status_code == 404:
        continue
    else:
        print(f'Failed to get logs for try {try_num}: {r2.status_code}')
        print(r2.text[:500])
        print()

PYEOF
