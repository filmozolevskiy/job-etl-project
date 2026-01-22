#!/bin/bash
# Create staging environment files for slots 2-10
#
# Usage:
#   POSTGRES_HOST=xxx POSTGRES_PORT=xxx POSTGRES_USER=xxx POSTGRES_PASSWORD=xxx ./create_staging_envs.sh
#
# Or source from .env.staging-1:
#   source ~/staging-1/.env.staging-1 && ./create_staging_envs.sh

# Use environment variables (must be set before running)
DB_HOST="${POSTGRES_HOST:?Error: POSTGRES_HOST not set}"
DB_PORT="${POSTGRES_PORT:?Error: POSTGRES_PORT not set}"
DB_USER="${POSTGRES_USER:?Error: POSTGRES_USER not set}"
DB_PASSWORD="${POSTGRES_PASSWORD:?Error: POSTGRES_PASSWORD not set}"

for SLOT in 2 3 4 5 6 7 8 9 10; do
  mkdir -p ~/staging-${SLOT}
  
  # Generate unique secrets for each slot
  FLASK_SECRET=$(openssl rand -base64 32 | tr -d "/+=" | head -c 43)
  JWT_SECRET=$(openssl rand -base64 32 | tr -d "/+=" | head -c 43)
  AIRFLOW_FERNET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  AIRFLOW_PASS="staging${SLOT}admin"
  
  # Calculate ports
  CAMPAIGN_PORT=$((5000 + SLOT))
  AIRFLOW_PORT=$((8080 + SLOT))
  FRONTEND_PORT_NUM=$((5173 + SLOT))
  
  cat > ~/staging-${SLOT}/.env.staging-${SLOT} << EOF
# Staging Slot ${SLOT} Environment
STAGING_SLOT=${SLOT}
ENVIRONMENT=staging

# Port Configuration
CAMPAIGN_UI_PORT=${CAMPAIGN_PORT}
AIRFLOW_WEBSERVER_PORT=${AIRFLOW_PORT}
FRONTEND_PORT=${FRONTEND_PORT_NUM}

# Database Configuration (DigitalOcean Managed PostgreSQL)
POSTGRES_HOST=${DB_HOST}
POSTGRES_PORT=${DB_PORT}
POSTGRES_USER=${DB_USER}
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_DB=job_search_staging_${SLOT}
POSTGRES_SSL_MODE=require

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=0
FLASK_SECRET_KEY=${FLASK_SECRET}
JWT_SECRET_KEY=${JWT_SECRET}

# Airflow Configuration
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=${AIRFLOW_PASS}
AIRFLOW_UID=50000
AIRFLOW_FERNET_KEY=${AIRFLOW_FERNET}
AIRFLOW_API_URL=http://airflow-webserver:8080/api/v1
AIRFLOW_API_USERNAME=admin
AIRFLOW_API_PASSWORD=${AIRFLOW_PASS}

# API Keys (add your actual keys)
JSEARCH_API_KEY=
GLASSDOOR_API_KEY=
OPENAI_API_KEY=

# ChatGPT Configuration
CHATGPT_MODEL=gpt-5-nano
CHATGPT_ENRICHMENT_BATCH_SIZE=10
CHATGPT_MAX_RETRIES=3

# Deployment Metadata (set by deploy script)
DEPLOYED_SHA=
DEPLOYED_BRANCH=
EOF

  chmod 600 ~/staging-${SLOT}/.env.staging-${SLOT}
  echo "Created staging-${SLOT} environment file"
done

echo ""
echo "All staging environment files created successfully!"
echo "Listing created directories:"
ls -la ~/staging-*/
