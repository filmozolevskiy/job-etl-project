#!/bin/bash
# Update docker-compose.staging.yml in all staging slots

for i in 1 2 3 4 5 6 7 8 9 10; do
    TARGET=~/staging-$i/job-search-project/docker-compose.staging.yml
    if [ -d "$(dirname $TARGET)" ]; then
        cp /tmp/docker-compose.staging.yml "$TARGET"
        echo "Updated slot $i"
    else
        echo "Skipping slot $i (not set up)"
    fi
done

echo "Done!"
