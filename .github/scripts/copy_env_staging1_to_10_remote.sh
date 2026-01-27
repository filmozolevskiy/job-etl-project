#!/bin/bash
set -euo pipefail
SRC=~/staging-1/.env.staging-1
DEST=~/staging-10/.env.staging-10
if [ ! -f "$SRC" ]; then
  echo "ERROR: $SRC not found"
  exit 1
fi
mkdir -p ~/staging-10
cp "$SRC" "$DEST"
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
echo "Created $DEST from $SRC"
ls -la "$DEST"
