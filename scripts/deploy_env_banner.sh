#!/bin/bash
# Deploy environment banner to all staging slots

for i in 1 2 3 4 5 6 7 8 9 10; do
    PROJ_DIR=~/staging-$i/job-search-project
    
    if [ -d "$PROJ_DIR" ]; then
        # Copy frontend files
        cp /tmp/EnvironmentBanner.tsx "$PROJ_DIR/frontend/src/components/"
        cp /tmp/Layout.tsx "$PROJ_DIR/frontend/src/components/"
        
        # Copy backend file
        cp /tmp/app.py "$PROJ_DIR/campaign_ui/"
        
        echo "Updated slot $i"
    else
        echo "Skipping slot $i (not configured)"
    fi
done

echo "Done updating files!"
