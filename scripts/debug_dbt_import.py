#!/usr/bin/env python3
"""Debug dbt by importing directly."""

import os

os.chdir("/opt/airflow/dbt")

print("=== Trying to import dbt ===")
try:
    from dbt.cli.main import dbtRunner

    print("Successfully imported dbt.cli.main")

    runner = dbtRunner()
    print("Created dbtRunner")

    # Try running debug
    print("\n=== Running dbt debug ===")
    result = runner.invoke(["debug", "--profiles-dir", "/opt/airflow/dbt"])
    print(f"Result type: {type(result)}")
    print(f"Result success: {result.success}")
    print(f"Result exception: {result.exception}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
