#!/bin/bash
# Create symlinks for .env files in project directories

for SLOT in 1 2 3 4 5 6 7 8 9 10; do
    PROJECT_DIR=~/staging-$SLOT/job-search-project
    ENV_FILE=~/staging-$SLOT/.env.staging-$SLOT
    
    if [ ! -d "$PROJECT_DIR" ]; then
        echo "Slot $SLOT: Skipped (not configured)"
        continue
    fi
    
    # Create symlinks
    cd "$PROJECT_DIR"
    
    # Link to .env.staging (what ENVIRONMENT=staging expects)
    ln -sf "$ENV_FILE" .env.staging
    
    # Link to .env (fallback)
    ln -sf "$ENV_FILE" .env
    
    echo "Slot $SLOT: Created symlinks"
done

echo ""
echo "Done!"
