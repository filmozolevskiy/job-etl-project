#!/bin/bash
# Fix port configurations in staging env files

for SLOT in 2 3 4 5 6 7 8 9 10; do
    ENV_FILE=~/staging-$SLOT/.env.staging-$SLOT
    
    if [ ! -f "$ENV_FILE" ]; then
        echo "Slot $SLOT: Skipped (no env file)"
        continue
    fi
    
    CAMPAIGN_UI_PORT=$((5000 + SLOT))
    AIRFLOW_PORT=$((8080 + SLOT))
    FRONTEND_PORT=$((5173 + SLOT))
    
    # Update the port values using sed
    sed -i "s/^CAMPAIGN_UI_PORT=.*/CAMPAIGN_UI_PORT=$CAMPAIGN_UI_PORT/" "$ENV_FILE"
    sed -i "s/^AIRFLOW_WEBSERVER_PORT=.*/AIRFLOW_WEBSERVER_PORT=$AIRFLOW_PORT/" "$ENV_FILE"
    sed -i "s/^FRONTEND_PORT=.*/FRONTEND_PORT=$FRONTEND_PORT/" "$ENV_FILE"
    
    echo "Slot $SLOT: Updated ports (UI=$CAMPAIGN_UI_PORT, Airflow=$AIRFLOW_PORT, Frontend=$FRONTEND_PORT)"
done

echo ""
echo "Done!"
