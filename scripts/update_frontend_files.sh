#!/bin/bash
# Update frontend nginx.conf and api.ts in all staging slots

for i in 1 2 3 4 5 6 7 8 9 10; do
    NGINX_DEST=~/staging-$i/job-search-project/frontend/nginx.conf
    API_DEST=~/staging-$i/job-search-project/frontend/src/services/api.ts
    
    if [ -d "$(dirname $NGINX_DEST)" ]; then
        cp /tmp/nginx.conf "$NGINX_DEST"
        cp /tmp/api.ts "$API_DEST"
        echo "Updated slot $i"
    else
        echo "Skipping slot $i (not configured)"
    fi
done

echo "Done!"
