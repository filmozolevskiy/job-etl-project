#!/usr/bin/env python3
"""Debug dbt environment and run."""
import subprocess
import os
import sys

print("=== Python Environment ===")
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")

print("\n=== Environment Variables ===")
for key in ["HOME", "USER", "POSTGRES_HOST", "POSTGRES_DB"]:
    print(f"{key}: {os.environ.get(key, 'NOT SET')}")

print("\n=== Working Directory ===")
os.chdir("/opt/airflow/dbt")
print(f"PWD: {os.getcwd()}")
print(f"Files: {os.listdir('.')}")

print("\n=== dbt Location ===")
result = subprocess.run(["which", "dbt"], capture_output=True, text=True)
print(f"dbt path: {result.stdout.strip()}")

print("\n=== profiles.yml Content ===")
with open("profiles.yml") as f:
    print(f.read())

print("\n=== Running dbt debug ===")
result = subprocess.run(
    ["dbt", "debug", "--profiles-dir", "/opt/airflow/dbt"],
    capture_output=True,
    text=True,
    cwd="/opt/airflow/dbt"
)
print(f"STDOUT: {result.stdout}")
print(f"STDERR: {result.stderr}")
print(f"Return code: {result.returncode}")
