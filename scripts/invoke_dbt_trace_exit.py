"""Invoke dbt CLI and trace sys.exit calls."""
import os
import sys

_real_exit = sys.exit
def traced_exit(code=0):
    import traceback
    print("sys.exit called with", code, file=sys.stderr)
    traceback.print_stack(file=sys.stderr)
    _real_exit(code)
sys.exit = traced_exit

os.chdir("/opt/airflow/dbt")
sys.argv = [
    "dbt", "run",
    "--select", "staging.jsearch_job_postings",
    "--profiles-dir", "/opt/airflow/dbt",
]
try:
    from dbt.cli.main import cli
    cli()
except SystemExit as e:
    print("SystemExit:", e.code, file=sys.stderr)
    _real_exit(e.code if e.code is not None else 1)
except Exception:
    import traceback
    traceback.print_exc()
    _real_exit(2)
