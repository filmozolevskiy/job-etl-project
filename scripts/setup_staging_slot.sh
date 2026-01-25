#!/bin/bash
# Setup a new staging slot on the droplet
#
# Usage:
#   ./setup_staging_slot.sh <slot_number> [branch]
#
# Example:
#   ./setup_staging_slot.sh 2 main
#   ./setup_staging_slot.sh 3 feature/my-branch

set -e

SLOT=${1:?Usage: $0 <slot_number> [branch]}
BRANCH=${2:-main}

# Configuration
SLOT_DIR=~/staging-$SLOT
PROJECT_DIR=$SLOT_DIR/job-search-project
ENV_FILE=$SLOT_DIR/.env.staging-$SLOT
REPO_URL="https://github.com/filmozolevskiy/job-etl-project.git"

# Port calculation
CAMPAIGN_UI_PORT=$((5000 + SLOT))
AIRFLOW_PORT=$((8080 + SLOT))
FRONTEND_PORT=$((5173 + SLOT))
LOCAL_POSTGRES_PORT=$((54320 + SLOT))

# Database
DB_NAME="job_search_staging_$SLOT"

echo "============================================"
echo "Setting up Staging Slot $SLOT"
echo "============================================"
echo "Branch: $BRANCH"
echo "Directory: $SLOT_DIR"
echo "Ports: UI=$CAMPAIGN_UI_PORT, Airflow=$AIRFLOW_PORT, Frontend=$FRONTEND_PORT"
echo "Database: $DB_NAME"
echo ""

# Check if already set up
if [ -d "$PROJECT_DIR" ]; then
    echo "WARNING: Slot $SLOT already has a git checkout"
    echo "To reset, run: rm -rf $PROJECT_DIR"
    exit 1
fi

# Create directory if needed
mkdir -p $SLOT_DIR

# Clone repository
echo "Cloning repository..."
if [ -d ~/staging-1/job-search-project ]; then
    # Clone from existing checkout (faster)
    git clone ~/staging-1/job-search-project $PROJECT_DIR
    cd $PROJECT_DIR
    git remote set-url origin $REPO_URL 2>/dev/null || true
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    # Clone from remote
    git clone $REPO_URL $PROJECT_DIR
    cd $PROJECT_DIR
    git checkout $BRANCH
fi

echo ""

# Generate unique secrets
echo "Generating unique secrets..."
FLASK_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
AIRFLOW_PASSWORD="staging${SLOT}admin"

echo ""

# Get database credentials from slot 1 (same PG instance)
echo "Getting database credentials..."
if [ -f ~/staging-1/.env.staging-1 ]; then
    source ~/staging-1/.env.staging-1
    PG_HOST=$POSTGRES_HOST
    PG_PORT=$POSTGRES_PORT
    PG_USER=$POSTGRES_USER
    PG_PASSWORD=$POSTGRES_PASSWORD
    JSEARCH_KEY=$JSEARCH_API_KEY
    GLASSDOOR_KEY=$GLASSDOOR_API_KEY
    OPENAI_KEY=$OPENAI_API_KEY
else
    echo "ERROR: Cannot find ~/staging-1/.env.staging-1"
    echo "Please set up slot 1 first or provide database credentials"
    exit 1
fi

echo ""

# Create .env file
echo "Creating environment file..."
cat > $ENV_FILE << EOF
# Staging Slot $SLOT Environment
STAGING_SLOT=$SLOT
ENVIRONMENT=staging

# Port Configuration
CAMPAIGN_UI_PORT=$CAMPAIGN_UI_PORT
AIRFLOW_WEBSERVER_PORT=$AIRFLOW_PORT
FRONTEND_PORT=$FRONTEND_PORT
LOCAL_POSTGRES_PORT=$LOCAL_POSTGRES_PORT

# Database Configuration (DigitalOcean Managed PostgreSQL)
POSTGRES_HOST=$PG_HOST
POSTGRES_PORT=$PG_PORT
POSTGRES_USER=$PG_USER
POSTGRES_PASSWORD=$PG_PASSWORD
POSTGRES_DB=$DB_NAME
POSTGRES_SSL_MODE=require

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=0
FLASK_SECRET_KEY=$FLASK_SECRET
JWT_SECRET_KEY=$JWT_SECRET

# Airflow Configuration
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=$AIRFLOW_PASSWORD
AIRFLOW_UID=50000
AIRFLOW_FERNET_KEY=$FERNET_KEY
AIRFLOW_API_URL=http://airflow-webserver:8080/api/v1
AIRFLOW_API_USERNAME=admin
AIRFLOW_API_PASSWORD=$AIRFLOW_PASSWORD

# API Keys
JSEARCH_API_KEY=$JSEARCH_KEY
GLASSDOOR_API_KEY=$GLASSDOOR_KEY
OPENAI_API_KEY=$OPENAI_KEY

# ChatGPT Configuration
CHATGPT_MODEL=gpt-5-nano
CHATGPT_ENRICHMENT_BATCH_SIZE=10
CHATGPT_MAX_RETRIES=3

# Deployment Metadata (set by deploy script)
DEPLOYED_SHA=$(cd $PROJECT_DIR && git rev-parse --short HEAD)
DEPLOYED_BRANCH=$BRANCH
DEPLOYED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

# Secure the env file
chmod 600 $ENV_FILE

# Create symlinks for Docker Compose env files
cd $PROJECT_DIR
ln -sf $ENV_FILE .env.staging
ln -sf $ENV_FILE .env

echo ""

# Summary
echo "============================================"
echo "Slot $SLOT setup complete!"
echo "============================================"
echo ""
echo "Environment file: $ENV_FILE"
echo "Project directory: $PROJECT_DIR"
echo ""
echo "To start the services:"
echo "  cd $PROJECT_DIR"
echo "  source $ENV_FILE"
echo "  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-$SLOT up -d"
echo ""
echo "To check status:"
echo "  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-$SLOT ps"
echo ""
