#!/bin/bash
# Start a staging slot's Docker stack
#
# Usage:
#   ./start_staging_slot.sh <slot_number>

set -e

SLOT=${1:?Usage: $0 <slot_number>}

SLOT_DIR=~/staging-$SLOT
PROJECT_DIR=$SLOT_DIR/job-search-project
ENV_FILE=$SLOT_DIR/.env.staging-$SLOT

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Slot $SLOT is not set up"
    echo "Run: /tmp/setup_staging_slot.sh $SLOT"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file not found: $ENV_FILE"
    exit 1
fi

echo "============================================"
echo "Starting Staging Slot $SLOT"
echo "============================================"

cd $PROJECT_DIR

# Source environment
echo "Loading environment..."
set -a  # Automatically export all variables
source $ENV_FILE
set +a

# Start services
echo "Starting Docker Compose stack..."
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-$SLOT up -d --build

echo ""
echo "Waiting for services to start..."
sleep 10

# Check status
echo ""
echo "Container status:"
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-$SLOT ps

echo ""
echo "============================================"
echo "Slot $SLOT started!"
echo "============================================"
echo ""
echo "Campaign UI: http://134.122.35.239:$CAMPAIGN_UI_PORT"
echo "Airflow UI:  http://134.122.35.239:$AIRFLOW_WEBSERVER_PORT"
echo ""
