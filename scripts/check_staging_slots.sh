#!/bin/bash
# Check setup status of all staging slots

echo "Staging Slot Status:"
echo "===================="
echo ""

for i in 1 2 3 4 5 6 7 8 9 10; do
    echo -n "Slot $i: "
    
    SLOT_DIR=~/staging-$i
    ENV_FILE=$SLOT_DIR/.env.staging-$i
    PROJECT_DIR=$SLOT_DIR/job-search-project
    
    if [ ! -d "$SLOT_DIR" ]; then
        echo "NOT SET UP (no directory)"
    elif [ ! -f "$ENV_FILE" ]; then
        echo "PARTIAL (directory exists, no .env file)"
    elif [ ! -d "$PROJECT_DIR" ]; then
        echo "PARTIAL (no git checkout)"
    else
        # Check if containers are running
        CONTAINERS=$(sg docker -c "docker compose -f $PROJECT_DIR/docker-compose.yml -f $PROJECT_DIR/docker-compose.staging.yml -p staging-$i ps -q 2>/dev/null" | wc -l)
        if [ "$CONTAINERS" -gt 0 ]; then
            echo "RUNNING ($CONTAINERS containers)"
        else
            echo "CONFIGURED (not running)"
        fi
    fi
done

echo ""
echo "Done!"
