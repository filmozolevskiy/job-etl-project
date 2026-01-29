#!/bin/bash
set -e
cd /home/deploy/staging-10/job-search-project
source /home/deploy/staging-10/.env.staging-10
# Create temp profile with hardcoded values
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c "
cd /opt/airflow/dbt
cp profiles.yml profiles.yml.bak
cat > profiles.yml << 'PROF'
job_search_platform:
  target: staging
  outputs:
    staging:
      type: postgres
      host: \"${POSTGRES_HOST}\"
      port: ${POSTGRES_PORT}
      user: \"${POSTGRES_USER}\"
      password: \"${POSTGRES_PASSWORD}\"
      dbname: \"${POSTGRES_DB}\"
      schema: dbt
      threads: 4
      sslmode: require
PROF
dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt -d --no-use-colors 2>&1
mv profiles.yml.bak profiles.yml
"
