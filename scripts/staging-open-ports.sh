#!/bin/bash
# Open UFW ports for a staging slot on the droplet.
# Run ON the droplet (e.g. ssh deploy@DROPLET_IP 'bash -s' -- < scripts/staging-open-ports.sh 1)
# Or copy and run there: ./staging-open-ports.sh 1 [optional: YOUR_IP]
#
# Usage: ./staging-open-ports.sh <slot> [source_ip]
#   slot: 1-9 (staging slot number)
#   source_ip: optional, e.g. 203.0.113.50 or 203.0.113.50/32; if omitted, allows from anywhere

set -euo pipefail

SLOT=${1:-}
SOURCE=${2:-}

if [[ -z "$SLOT" ]] || [[ ! "$SLOT" =~ ^[1-9]$ ]]; then
  echo "Usage: $0 <slot> [source_ip]"
  echo "  slot: 1-9"
  echo "  source_ip: optional; if omitted, ports are allowed from anywhere"
  exit 1
fi

CAMPAIGN_PORT=$((5000 + SLOT))
AIRFLOW_PORT=$((8080 + SLOT))

if [[ -n "$SOURCE" ]]; then
  echo "Allowing $SOURCE to ports $CAMPAIGN_PORT and $AIRFLOW_PORT..."
  sudo ufw allow from "$SOURCE" to any port "$CAMPAIGN_PORT" proto tcp
  sudo ufw allow from "$SOURCE" to any port "$AIRFLOW_PORT" proto tcp
else
  echo "Allowing anyone to ports $CAMPAIGN_PORT and $AIRFLOW_PORT..."
  sudo ufw allow "$CAMPAIGN_PORT/tcp"
  sudo ufw allow "$AIRFLOW_PORT/tcp"
fi

sudo ufw reload
echo "Done. Staging-$SLOT: Campaign UI port $CAMPAIGN_PORT, Airflow port $AIRFLOW_PORT."
