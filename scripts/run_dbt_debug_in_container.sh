#!/bin/bash
set -e
cd /home/deploy/staging-10/job-search-project
echo "=== target and logs ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "cd /opt/airflow/dbt && ls -la target/ 2>/dev/null || true && ls -la logs/ 2>/dev/null || true"
echo "=== dbt debug via python ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler python3 << 'PY'
import subprocess, os
r = subprocess.run(["dbt", "debug"], cwd="/opt/airflow/dbt", capture_output=True, text=True, env=os.environ)
print("returncode", r.returncode)
print("stdout", repr(r.stdout))
print("stderr", repr(r.stderr))
PY
