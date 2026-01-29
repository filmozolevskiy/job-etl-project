"""Invoke dbt run and capture any Python exception."""

import os
import sys

os.chdir("/opt/airflow/dbt")
sys.path.insert(0, "/opt/airflow/dbt")


def main():
    try:
        import dbt.main

        # argv: dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt
        sys.argv = [
            "dbt",
            "run",
            "--select",
            "staging.jsearch_job_postings",
            "--profiles-dir",
            "/opt/airflow/dbt",
        ]
        dbt.main.main()
    except SystemExit as e:
        print(f"SystemExit: {e.code}", file=sys.stderr)
        raise
    except Exception as e:
        import traceback

        print("Exception:", e, file=sys.stderr)
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
