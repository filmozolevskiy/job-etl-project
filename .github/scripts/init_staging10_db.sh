#!/bin/bash
# Initialize staging-10 database with all schemas and tables

set -euo pipefail
source ~/staging-10/.env.staging-10

echo "=== Initializing staging-10 database ==="
cd /home/deploy/staging-10/job-search-project

# Run init scripts in order
for script in docker/init/0*.sql docker/init/1*.sql docker/init/99*.sql; do
    if [ -f "$script" ]; then
        echo "Running $script..."
        PGPASSWORD="${POSTGRES_PASSWORD}" psql \
            -h "${POSTGRES_HOST}" \
            -p "${POSTGRES_PORT}" \
            -U "${POSTGRES_USER}" \
            -d "${POSTGRES_DB}" \
            -f "$script" \
            2>&1 | grep -v "already exists" || true
    fi
done

echo ""
echo "=== Verifying schemas ==="
PGPASSWORD="${POSTGRES_PASSWORD}" psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('dbt', 'raw', 'staging', 'marts') ORDER BY schema_name;"

echo ""
echo "=== Verifying marts tables ==="
PGPASSWORD="${POSTGRES_PASSWORD}" psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts' ORDER BY table_name;"

echo ""
echo "✅ Database initialization complete"
