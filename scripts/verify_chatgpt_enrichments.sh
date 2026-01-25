#!/bin/bash
# Verify chatgpt_enrichments table exists in all staging databases

source ~/staging-1/.env.staging-1
export PGPASSWORD="$POSTGRES_PASSWORD"

echo "Verifying staging.chatgpt_enrichments table exists:"
echo ""

for i in 1 2 3 4 5 6 7 8 9 10; do
    DB_NAME="job_search_staging_$i"
    EXISTS=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$DB_NAME" -t -c "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='staging' AND table_name='chatgpt_enrichments')" 2>/dev/null)
    
    if [ "$(echo $EXISTS | tr -d ' ')" = "t" ]; then
        echo "  Slot $i: ✓ OK"
    else
        echo "  Slot $i: ✗ MISSING"
    fi
done

echo ""
echo "Done!"
