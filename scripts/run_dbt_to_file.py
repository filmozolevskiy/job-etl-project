"""Run dbt and write stdout/stderr to a file, then print it."""

import subprocess
import sys

log_path = "/tmp/dbt_run_capture.log"
cmd = [
    "dbt",
    "run",
    "--select",
    "staging.jsearch_job_postings",
    "--profiles-dir",
    "/opt/airflow/dbt",
]
with open(log_path, "w") as f:
    r = subprocess.run(
        cmd,
        cwd="/opt/airflow/dbt",
        stdout=f,
        stderr=subprocess.STDOUT,
        text=True,
        env={"PYTHONUNBUFFERED": "1", **__import__("os").environ},
    )
with open(log_path) as f:
    out = f.read()
print("=== CAPTURED OUTPUT ===")
print(out)
print("=== EXIT CODE ===", r.returncode)
sys.exit(r.returncode)
