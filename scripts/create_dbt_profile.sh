#!/bin/bash
# Create dbt profiles.yml in Airflow scheduler container

sg docker -c 'docker exec staging_1_airflow_scheduler bash -c "cat > /opt/airflow/dbt/profiles.yml << EOF
job_search_platform:
  target: staging
  outputs:
    staging:
      type: postgres
      host: \"{{ env_var('POSTGRES_HOST', 'localhost') }}\"
      port: \"{{ env_var('POSTGRES_PORT', '5432') | as_number }}\"
      user: \"{{ env_var('POSTGRES_USER', 'postgres') }}\"
      password: \"{{ env_var('POSTGRES_PASSWORD', 'postgres') }}\"
      dbname: \"{{ env_var('POSTGRES_DB', 'job_search_db') }}\"
      schema: dbt
      threads: 4
      keepalives_idle: 0
      connect_timeout: 10
      sslmode: require
EOF
"'

# Verify the file was created
echo ""
echo "=== Verifying profiles.yml ==="
sg docker -c 'docker exec staging_1_airflow_scheduler cat /opt/airflow/dbt/profiles.yml'
