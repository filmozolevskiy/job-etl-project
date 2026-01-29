"""Run dbt without capturing output - inherit stdout/stderr."""
import os
import subprocess
import sys

cmd = [
    "dbt", "run",
    "--select", "staging.jsearch_job_postings",
    "--profiles-dir", "/opt/airflow/dbt",
]
os.chdir("/opt/airflow/dbt")
env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"
print("Running:", " ".join(cmd), flush=True)
sys.stdout.flush()
sys.stderr.flush()
r = subprocess.run(cmd, env=env, cwd="/opt/airflow/dbt")
print("Exit code:", r.returncode, flush=True)
sys.exit(r.returncode)
