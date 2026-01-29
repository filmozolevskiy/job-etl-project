"""Invoke dbt CLI directly and catch exceptions."""
import os
import sys

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
    sys.exit(e.code if e.code is not None else 1)
except Exception as e:
    import traceback
    print("Exception:", e, file=sys.stderr)
    traceback.print_exc()
    sys.exit(2)
