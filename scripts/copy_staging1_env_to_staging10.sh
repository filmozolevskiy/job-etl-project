#!/bin/bash
# Copy staging-1 env to staging-10 and adapt slot-specific values.
# Run on the droplet (e.g. via SSH).
#
# Usage:
#   ./scripts/copy_staging1_env_to_staging10.sh
#
# Prerequisites:
#   - ~/staging-1/.env.staging-1 exists

set -euo pipefail

SRC="${HOME}/staging-1/.env.staging-1"
DEST_DIR="${HOME}/staging-10"
DEST="${DEST_DIR}/.env.staging-10"

if [ ! -f "$SRC" ]; then
  echo "ERROR: Source env not found: $SRC"
  echo "Set up staging-1 first (see project_documentation/deployment-staging.md)."
  exit 1
fi

mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST"

# Adapt slot-specific values (1 -> 10)
sed -i.bak \
  -e 's/^STAGING_SLOT=1$/STAGING_SLOT=10/' \
  -e 's/^CAMPAIGN_UI_PORT=5001$/CAMPAIGN_UI_PORT=5010/' \
  -e 's/^AIRFLOW_WEBSERVER_PORT=8081$/AIRFLOW_WEBSERVER_PORT=8090/' \
  -e 's/^FRONTEND_PORT=5174$/FRONTEND_PORT=5183/' \
  -e 's/^POSTGRES_DB=job_search_staging_1$/POSTGRES_DB=job_search_staging_10/' \
  -e 's/staging1admin/staging10admin/g' \
  "$DEST"
rm -f "${DEST}.bak"

chmod 600 "$DEST"
echo "Created $DEST from $SRC (slot 10 ports, DB, Airflow password)."
echo "Ensure job_search_staging_10 exists on the Postgres instance."
