#!/bin/bash
# Create databases for staging slots 2-10 on DigitalOcean Managed PostgreSQL
#
# Usage:
#   DB_HOST=xxx DB_PORT=xxx DB_USER=xxx DB_PASSWORD=xxx ./create_staging_dbs.sh
#
# Or source from .env.staging-1:
#   source ~/staging-1/.env.staging-1 && ./create_staging_dbs.sh

# Use environment variables (must be set before running)
DB_HOST="${POSTGRES_HOST:?Error: POSTGRES_HOST not set}"
DB_PORT="${POSTGRES_PORT:?Error: POSTGRES_PORT not set}"
DB_USER="${POSTGRES_USER:?Error: POSTGRES_USER not set}"
DB_PASSWORD="${POSTGRES_PASSWORD:?Error: POSTGRES_PASSWORD not set}"

for SLOT in 2 3 4 5 6 7 8 9 10; do
  DB_NAME="job_search_staging_${SLOT}"
  echo "Creating database ${DB_NAME}..."
  PGPASSWORD=${DB_PASSWORD} psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d defaultdb -c "CREATE DATABASE ${DB_NAME};" 2>&1 || echo "Database ${DB_NAME} may already exist"
done

echo ""
echo "Listing all databases:"
PGPASSWORD=${DB_PASSWORD} psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d defaultdb -c "\l" | grep job_search
