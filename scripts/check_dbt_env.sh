#!/bin/bash
# Check dbt environment

sg docker -c 'docker exec staging_1_airflow_scheduler python3 << PYEOF
import subprocess
import os
import sys

print("=== Environment ===")
print(f"HOME: {os.environ.get(chr(72)+chr(79)+chr(77)+chr(69))}")
print(f"USER: {os.environ.get(chr(85)+chr(83)+chr(69)+chr(82))}")
print(f"PWD: {os.getcwd()}")

print("\n=== dbt location ===")
result = subprocess.run(["which", "dbt"], capture_output=True, text=True)
print(f"dbt path: {result.stdout.strip()}")

print("\n=== Check profiles.yml ===")
profiles_path = "/opt/airflow/dbt/profiles.yml"
if os.path.exists(profiles_path):
    print(f"profiles.yml exists at {profiles_path}")
    with open(profiles_path) as f:
        print(f.read())
else:
    print(f"profiles.yml NOT FOUND at {profiles_path}")
    
# Check home directory profiles
home_profiles = os.path.expanduser("~/.dbt/profiles.yml")
if os.path.exists(home_profiles):
    print(f"\nHome profiles.yml exists at {home_profiles}")
else:
    print(f"\nNo home profiles.yml at {home_profiles}")

print("\n=== dbt_project.yml ===")
project_path = "/opt/airflow/dbt/dbt_project.yml"
if os.path.exists(project_path):
    print(f"dbt_project.yml exists at {project_path}")
else:
    print(f"dbt_project.yml NOT FOUND at {project_path}")
PYEOF'
