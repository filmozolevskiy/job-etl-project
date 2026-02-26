#!/bin/bash
# Restart a staging slot's Docker stack without pulling or rebuilding.
#
# Usage:
#   ./scripts/restart_staging_slot.sh <slot_number>

set -euo pipefail

SLOT=${1:?Usage: $0 <slot_number>}

SLOT_DIR=~/staging-$SLOT
PROJECT_DIR=$SLOT_DIR/job-search-project
ENV_FILE=$SLOT_DIR/.env.staging-$SLOT

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Slot $SLOT is not set up. Run provision_staging_slot.sh first."
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file not found: $ENV_FILE"
    exit 1
fi

echo "============================================"
echo "Restarting Staging Slot $SLOT"
echo "============================================"

cd "$PROJECT_DIR"

# Source environment
echo "Loading environment..."
set -a
source "$ENV_FILE"
set +a
# Standardize credentials: admin/admin123 for all stagings
export AIRFLOW_PASSWORD=admin123
export AIRFLOW_API_PASSWORD=admin123
export AIRFLOW_API_USERNAME=admin
export AIRFLOW_USERNAME=admin
echo "✓ Environment loaded."

# Start services
echo "Starting Docker Compose stack..."
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-$SLOT" up -d
echo "✓ Docker Compose up command executed."

echo ""
echo "Waiting for services to start..."
sleep 10

# Check status
echo ""
echo "Container status:"
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-$SLOT" ps

echo ""
echo "============================================"
echo "✓ Slot $SLOT restarted!"
echo "============================================"
echo ""
echo "Backend API: https://staging-${SLOT}.justapply.net"
echo "Airflow UI:  https://staging-${SLOT}.justapply.net/airflow/"
echo ""
