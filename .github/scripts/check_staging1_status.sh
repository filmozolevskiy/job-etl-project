#!/bin/bash
# Check if staging-1 is working and compare with staging-10

echo "=== Staging-1 Container Status ==="
cd /home/deploy/staging-1/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 ps -a | grep airflow || echo "Containers not running"

echo ""
echo "=== Staging-1 Latest DAG Run Status ==="
if docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 ps -q airflow-scheduler > /dev/null 2>&1; then
  python3 << 'PYEOF'
import requests
from requests.auth import HTTPBasicAuth

AUTH = HTTPBasicAuth('admin', 'staging1admin')
try:
    r = requests.get('http://localhost:8081/api/v1/dags/jobs_etl_daily/dagRuns?limit=1&order_by=-start_date', auth=AUTH, timeout=5)
    if r.status_code == 200:
        dag_runs = r.json().get('dag_runs', [])
        if dag_runs:
            dag_run = dag_runs[0]
            print(f"DAG Run ID: {dag_run.get('dag_run_id')}")
            print(f"State: {dag_run.get('state')}")
            print(f"Start: {dag_run.get('start_date')}")
            
            r2 = requests.get(f"http://localhost:8081/api/v1/dags/jobs_etl_daily/dagRuns/{dag_run.get('dag_run_id')}/taskInstances", auth=AUTH, timeout=5)
            if r2.status_code == 200:
                tasks = r2.json().get('task_instances', [])
                normalize_task = [t for t in tasks if t.get('task_id') == 'normalize_jobs']
                if normalize_task:
                    print(f"normalize_jobs state: {normalize_task[0].get('state')}")
                    print(f"Try number: {normalize_task[0].get('try_number')}")
        else:
            print("No DAG runs found")
    else:
        print(f"API error: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
PYEOF
else
  echo "Airflow scheduler not running"
fi

echo ""
echo "=== Staging-10 Latest DAG Run Status ==="
cd /home/deploy/staging-10/job-search-project
python3 << 'PYEOF'
import requests
from requests.auth import HTTPBasicAuth

AUTH = HTTPBasicAuth('admin', 'staging10admin')
try:
    r = requests.get('http://localhost:8090/api/v1/dags/jobs_etl_daily/dagRuns?limit=1&order_by=-start_date', auth=AUTH, timeout=5)
    if r.status_code == 200:
        dag_runs = r.json().get('dag_runs', [])
        if dag_runs:
            dag_run = dag_runs[0]
            print(f"DAG Run ID: {dag_run.get('dag_run_id')}")
            print(f"State: {dag_run.get('state')}")
            print(f"Start: {dag_run.get('start_date')}")
            
            r2 = requests.get(f"http://localhost:8090/api/v1/dags/jobs_etl_daily/dagRuns/{dag_run.get('dag_run_id')}/taskInstances", auth=AUTH, timeout=5)
            if r2.status_code == 200:
                tasks = r2.json().get('task_instances', [])
                normalize_task = [t for t in tasks if t.get('task_id') == 'normalize_jobs']
                if normalize_task:
                    print(f"normalize_jobs state: {normalize_task[0].get('state')}")
                    print(f"Try number: {normalize_task[0].get('try_number')}")
        else:
            print("No DAG runs found")
    else:
        print(f"API error: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
PYEOF
