"""Invoke dbt CLI with logging forced to stderr."""

import logging
import os
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
    force=True,
)
os.chdir("/opt/airflow/dbt")
sys.argv = [
    "dbt",
    "run",
    "--select",
    "staging.jsearch_job_postings",
    "--profiles-dir",
    "/opt/airflow/dbt",
]
try:
    from dbt.cli.main import cli

    cli()
except SystemExit as e:
    print("SystemExit:", e.code, file=sys.stderr)
    sys.exit(e.code if e.code is not None else 1)
except Exception:
    import traceback

    traceback.print_exc()
    sys.exit(2)
