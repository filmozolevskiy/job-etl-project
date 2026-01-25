#!/bin/bash
# Fix postgres port configuration for all staging slots
# - Updates docker-compose files
# - Adds LOCAL_POSTGRES_PORT to env files

echo "Updating all staging slots..."

for SLOT in 1 2 3 4 5 6 7 8 9 10; do
    PROJECT_DIR=~/staging-$SLOT/job-search-project
    ENV_FILE=~/staging-$SLOT/.env.staging-$SLOT
    
    if [ ! -d "$PROJECT_DIR" ]; then
        echo "Slot $SLOT: Skipped (not configured)"
        continue
    fi
    
    # Update docker-compose files
    cp /tmp/docker-compose.yml "$PROJECT_DIR/"
    cp /tmp/docker-compose.staging.yml "$PROJECT_DIR/"
    
    # Add LOCAL_POSTGRES_PORT if not already present
    if ! grep -q "LOCAL_POSTGRES_PORT" "$ENV_FILE" 2>/dev/null; then
        LOCAL_PORT=$((54320 + SLOT))
        echo "" >> "$ENV_FILE"
        echo "# Local postgres port (for noop container in staging)" >> "$ENV_FILE"
        echo "LOCAL_POSTGRES_PORT=$LOCAL_PORT" >> "$ENV_FILE"
        echo "Slot $SLOT: Updated (LOCAL_POSTGRES_PORT=$LOCAL_PORT)"
    else
        echo "Slot $SLOT: Updated (LOCAL_POSTGRES_PORT already set)"
    fi
done

echo ""
echo "Done!"
