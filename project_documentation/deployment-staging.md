# Staging Deployment (DigitalOcean)

This document captures the staging setup steps for the DigitalOcean droplet and
managed PostgreSQL instance. The staging environment supports **10 independent
staging slots** on a single droplet for parallel testing.

## Overview

The multi-staging architecture provides:

- **10 staging slots** (`staging-1` through `staging-10`)
- Each slot has its own Docker Compose stack, database, and subdomain
- Slots can be used independently by different developers or CI agents
- All slots share a single DigitalOcean droplet and managed PostgreSQL instance

### Port and Subdomain Mapping

| Slot | Subdomain | Campaign UI | Airflow | Frontend | Database |
|------|-----------|-------------|---------|----------|----------|
| 1 | `staging-1.justapply.net` | 5001 | 8081 | 5174 | `job_search_staging_1` |
| 2 | `staging-2.justapply.net` | 5002 | 8082 | 5175 | `job_search_staging_2` |
| 3 | `staging-3.justapply.net` | 5003 | 8083 | 5176 | `job_search_staging_3` |
| ... | ... | ... | ... | ... | ... |
| 10 | `staging-10.justapply.net` | 5010 | 8090 | 5183 | `job_search_staging_10` |

See `project_documentation/staging-slots.md` for the slot registry and ownership rules.

## 1) Droplet Hardening and Access

### 1.1 Connect to the droplet

```bash
ssh root@<DROPLET_IP>
```

### 1.2 Create a non-root user and enable sudo

```bash
adduser deploy
usermod -aG sudo deploy
```

### 1.3 Set timezone and update packages

```bash
timedatectl set-timezone UTC
apt update && apt -y upgrade
```

### 1.4 Configure SSH hardening

1) Copy your SSH key to the new user:

```bash
rsync --archive --chown=deploy:deploy /root/.ssh /home/deploy
```

2) Edit SSH config:

```bash
nano /etc/ssh/sshd_config
```

Set or verify:

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Restart SSH:

```bash
systemctl restart ssh
```

### 1.5 Configure firewall (UFW)

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow from <YOUR_IP>/32 to any port 8080 proto tcp
ufw allow from <YOUR_IP>/32 to any port 5000 proto tcp
ufw enable
ufw status
```

Staging values used:

- Droplet IP: `134.122.35.239`
- Allowed admin IP: `184.145.148.5`
- Hostname set: `staging-job-search`

### 1.6 Install Fail2ban

```bash
apt -y install fail2ban
systemctl enable --now fail2ban
```

### 1.7 Set hostname

```bash
hostnamectl set-hostname staging.justapply.net
```

Update `/etc/hosts` to include:

```
127.0.1.1 staging.justapply.net
```

## 2) DigitalOcean Firewall (Optional but recommended)

If using a DigitalOcean firewall, configure:

- Allow SSH (22) from your IP
- Allow HTTP (80) from anywhere
- Allow HTTPS (443) from anywhere
- Allow Airflow UI (8080) from your IP
- Allow Campaign UI (5000) from your IP

## 3) Managed PostgreSQL (Staging)

### 3.1 Create the database

#### Option A: Using DigitalOcean Console (Recommended for first-time setup)

1. Log in to [DigitalOcean Console](https://cloud.digitalocean.com/)
2. Navigate to **Databases** → **Create Database Cluster**
3. Configure the database:
   - **Database Engine**: PostgreSQL
   - **Version**: PostgreSQL 15
   - **Datacenter Region**: Same region as staging droplet (check droplet region in Droplets section)
   - **Plan**: Basic ($15/month)
     - 1GB RAM
     - 10GB storage
     - 1 vCPU
   - **Database Name**: `job_search_staging`
   - **Enable Connection Pooling**: Yes (recommended)
   - **Enable Automated Backups**: Yes
     - Retention: 7 days
     - Backup window: Choose off-peak hours
4. Click **Create Database Cluster**
5. Wait for cluster creation (5-10 minutes)

#### Option B: Using DigitalOcean API (doctl CLI)

**Prerequisites:**
- Install `doctl`: https://docs.digitalocean.com/reference/doctl/how-to/install/
- Authenticate: `doctl auth init`

**Create database cluster:**

```bash
# First, determine the droplet region
# Check your droplet region in DigitalOcean console or via:
doctl compute droplet list

# Create the database cluster
# Replace <REGION> with your droplet region (e.g., nyc1, sfo3, ams3)
doctl databases create job-search-staging-db \
  --engine pg \
  --version 15 \
  --region <REGION> \
  --size db-s-1vcpu-1gb \
  --num-nodes 1

# Wait for cluster to be ready (check status)
doctl databases list

# Once ready, get the cluster ID
CLUSTER_ID=$(doctl databases list --format ID,Name --no-header | grep job-search-staging-db | awk '{print $1}')

# Create the database
doctl databases db create $CLUSTER_ID job_search_staging

# Enable connection pooler (if not enabled by default)
# Note: Connection pooler is typically enabled by default for PostgreSQL clusters
```

### 3.2 Configure firewall rules

Restrict database access to only the staging droplet:

#### Using DigitalOcean Console:

1. Navigate to your database cluster → **Settings** → **Trusted Sources**
2. Click **Add Trusted Source**
3. Add the staging droplet IP: `134.122.35.239`
4. Save changes

#### Using doctl CLI:

```bash
# Get cluster ID (if not already set)
CLUSTER_ID=$(doctl databases list --format ID,Name --no-header | grep job-search-staging-db | awk '{print $1}')

# Add droplet IP to trusted sources
doctl databases firewalls append $CLUSTER_ID \
  --rule type:droplet,droplet_id:<DROPLET_ID>

# Or add by IP address
doctl databases firewalls append $CLUSTER_ID \
  --rule type:ip_addr,value:134.122.35.239
```

**Note:** Replace `<DROPLET_ID>` with your actual droplet ID (find via `doctl compute droplet list`).

### 3.3 Retrieve connection details

#### Using DigitalOcean Console:

1. Navigate to your database cluster → **Connection Details**
2. Copy the following information:
   - **Host**: Database hostname
   - **Port**: 
     - Standard port: `25060` (if connection pooler enabled)
     - Direct port: `25061` (bypasses pooler)
   - **Database**: `job_search_staging`
   - **User**: Default user (usually `doadmin`)
   - **Password**: Click **Show** to reveal password
   - **Connection String**: Full PostgreSQL connection string

#### Using doctl CLI:

```bash
# Get cluster ID
CLUSTER_ID=$(doctl databases list --format ID,Name --no-header | grep job-search-staging-db | awk '{print $1}')

# Get connection details
doctl databases connection $CLUSTER_ID

# Get connection pooler details (if enabled)
doctl databases pool $CLUSTER_ID --format Host,Port,User,Database,SSLMode
```

### 3.4 Save connection details securely

**IMPORTANT:** Store these values securely (password manager or secret manager):

- `POSTGRES_HOST`: Database hostname (e.g., `db-postgresql-nyc1-12345.db.ondigitalocean.com`)
- `POSTGRES_PORT`: 
  - Connection pooler: `25060` (recommended for application connections)
  - Direct connection: `25061` (for admin/maintenance)
- `POSTGRES_USER`: Default user (usually `doadmin`)
- `POSTGRES_PASSWORD`: Generated password (save immediately, cannot be retrieved later)
- `POSTGRES_DB`: `job_search_staging`
- `POSTGRES_SSL_MODE`: `require` (DigitalOcean requires SSL)

**Full connection string format:**
```
postgresql://doadmin:<PASSWORD>@<HOST>:25060/job_search_staging?sslmode=require
```

**Store in environment variables on droplet:**

```bash
# On staging droplet, create/update .env.staging
nano ~/.env.staging

# Add database configuration:
POSTGRES_HOST=<HOST>
POSTGRES_PORT=25060
POSTGRES_USER=doadmin
POSTGRES_PASSWORD=<PASSWORD>
POSTGRES_DB=job_search_staging
POSTGRES_SSL_MODE=require

# Secure the file
chmod 600 ~/.env.staging
```

### 3.5 Test connection from the droplet

```bash
# SSH to staging droplet
ssh deploy@134.122.35.239

# Install PostgreSQL client
sudo apt -y update
sudo apt -y install postgresql-client

# Test connection using connection pooler port
PGPASSWORD="<POSTGRES_PASSWORD>" psql \
  -h "<POSTGRES_HOST>" \
  -p 25060 \
  -U "doadmin" \
  -d "job_search_staging" \
  -c "SELECT version();"

# Expected output: PostgreSQL version information
# If successful, you should see PostgreSQL 15.x version string

# Test with SSL (required by DigitalOcean)
PGPASSWORD="<POSTGRES_PASSWORD>" psql \
  "postgresql://doadmin:<POSTGRES_PASSWORD>@<POSTGRES_HOST>:25060/job_search_staging?sslmode=require" \
  -c "SELECT current_database(), current_user;"

# Expected: Shows database name and user
```

### 3.6 Verify connection pooler (if enabled)

```bash
# Check pooler status via doctl
doctl databases pool $CLUSTER_ID

# Or test pooler connection
PGPASSWORD="<POSTGRES_PASSWORD>" psql \
  -h "<POSTGRES_HOST>" \
  -p 25060 \
  -U "doadmin" \
  -d "job_search_staging" \
  -c "SHOW pool_mode;"
```

### 3.7 Initialize database schema

After successful connection, initialize the database schema:

```bash
# On staging droplet, clone repository (if not already done)
cd ~
git clone <REPO_URL> job-search-project
cd job-search-project

# Load environment variables
export ENVIRONMENT=staging
source scripts/load_env.sh staging

# Run database initialization scripts
# These scripts create schemas and tables
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=require" \
  -f docker/init/01_create_schemas.sql
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=require" \
  -f docker/init/02_create_tables.sql

# Verify schemas created
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=require" \
  -c "\dn"
```

**Expected output:** Should show `raw`, `staging`, and `marts` schemas.

## 4) Environment Variables

Set staging secrets on the droplet in `.env.staging`:

```bash
chmod 600 .env.staging
```

Refer to `project_documentation/deployment-environments.md` for the full list of
required variables.

## 5) Verification Checklist

- SSH access works with the `deploy` user.
- Root login disabled; password auth disabled.
- UFW or DO firewall restricts 8080 and 5000 to your IP.
- Hostname is set.
- Fail2ban is running.
- Managed Postgres is reachable from the droplet.
- Connection string stored securely.

## 6) Install Docker and Docker Compose

### 6.1 Install Docker Engine

```bash
# SSH to staging droplet
ssh deploy@134.122.35.239

# Update packages
sudo apt update

# Install prerequisites
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 6.2 Configure Docker for Non-Root User

```bash
# Add deploy user to docker group
sudo usermod -aG docker deploy

# Apply new group membership (logout/login required for full effect)
newgrp docker

# Verify docker works without sudo
docker run hello-world
```

### 6.3 Configure Docker to Start on Boot

```bash
sudo systemctl enable docker
sudo systemctl enable containerd
```

### 6.4 Verification

```bash
# Check Docker status
sudo systemctl status docker

# Test docker compose
docker compose version

# Run test container
docker run --rm hello-world
```

## 7) Multi-Staging Database Setup

### 7.1 Create 10 Staging Databases

Using the DigitalOcean console or `doctl` CLI, create 10 databases on the managed
PostgreSQL cluster:

```bash
# Get cluster ID
CLUSTER_ID=$(doctl databases list --format ID,Name --no-header | grep job-search-staging-db | awk '{print $1}')

# Create databases for each staging slot
for i in {1..10}; do
    doctl databases db create $CLUSTER_ID job_search_staging_$i
    echo "Created database: job_search_staging_$i"
done

# Verify databases were created
doctl databases db list $CLUSTER_ID
```

### 7.2 Initialize Schema for Each Database

For each staging slot, run the initialization scripts:

```bash
# On staging droplet
cd /home/deploy/staging-1/job-search-project

# Load environment for slot 1
source /home/deploy/staging-1/.env.staging-1

# Initialize schemas
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=require" \
  -f docker/init/01_create_schemas.sql

# Create tables
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=require" \
  -f docker/init/02_create_tables.sql

# Run all migrations in order
for script in docker/init/0*.sql; do
    echo "Running $script..."
    psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=require" \
      -f "$script"
done

# Verify schemas
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=require" \
  -c "\dn"
```

Repeat for each staging slot (1-10), updating the slot number in paths and env files.

### 7.3 Test dbt Connection

```bash
cd /home/deploy/staging-1/job-search-project/dbt

# Test dbt connection
dbt debug --profiles-dir . --profile job_search_platform

# Run dbt models to verify data flow
dbt run --profiles-dir . --profile job_search_platform
```

## 8) Environment File Setup

### 8.1 Create Environment Files

For each staging slot, create an environment file based on the template:

```bash
# On staging droplet
mkdir -p /home/deploy/staging-1
cp /home/deploy/staging-1/job-search-project/.env.staging.template \
   /home/deploy/staging-1/.env.staging-1

# Edit with actual values
nano /home/deploy/staging-1/.env.staging-1

# Secure the file
chmod 600 /home/deploy/staging-1/.env.staging-1
```

### 8.2 Key Environment Variables per Slot

Each `.env.staging-N` file must have unique values for:

- `STAGING_SLOT=N` (1-10)
- `CAMPAIGN_UI_PORT=500N`
- `AIRFLOW_WEBSERVER_PORT=808N`
- `FRONTEND_PORT=517N+1`
- `POSTGRES_DB=job_search_staging_N`
- Unique `FLASK_SECRET_KEY` and `JWT_SECRET_KEY`
- Unique `AIRFLOW_FERNET_KEY`

## 9) Deploy Application

### 9.1 Using the Deploy Script

From your local machine with SSH access:

```bash
# Production (slot 10): deploy remote main, no staging banner
./scripts/deploy-production.sh

# Deploy to slot 1
./scripts/deploy-staging.sh 1 main

# Deploy a specific branch to slot 2
./scripts/deploy-staging.sh 2 feature/my-branch
```

Slot 10 is reserved as production until a dedicated production environment exists. See `project_documentation/staging-slots.md`.

### 9.2 Manual Deployment

If the script isn't available:

```bash
# SSH to staging droplet
ssh deploy@134.122.35.239

# Navigate to slot directory
cd /home/deploy/staging-1/job-search-project

# Pull latest code
git fetch origin
git checkout main
git pull origin main

# Load environment variables
export STAGING_SLOT=1
source /home/deploy/staging-1/.env.staging-1

# Stop existing containers
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 down

# Build and start
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 build
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 up -d

# Check status
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 ps
```

### 9.3 Verify Deployment

```bash
# Check container health
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 ps

# Check logs
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 logs -f --tail=100

# Test Campaign UI
curl http://localhost:5001/api/health

# Test Airflow
curl http://localhost:8081/health
```

## 10) Domain and SSL Configuration

### 10.1 DNS Configuration

Add DNS A records for all staging subdomains pointing to the staging droplet IP:

```
staging-1.justapply.net  A  134.122.35.239
staging-2.justapply.net  A  134.122.35.239
...
staging-10.justapply.net A  134.122.35.239
```

Or use a wildcard record:

```
*.justapply.net  A  134.122.35.239
```

### 10.2 Install Nginx

```bash
sudo apt update
sudo apt install -y nginx

# Enable and start nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 10.3 Configure Nginx

```bash
# Copy the multi-staging nginx config
sudo cp /home/deploy/staging-1/job-search-project/infra/nginx/staging-multi.conf \
        /etc/nginx/sites-available/staging-multi

# Enable the site
sudo ln -s /etc/nginx/sites-available/staging-multi /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 10.4 SSL Certificates

Run the SSL setup script:

```bash
# For wildcard certificate (recommended)
sudo /home/deploy/staging-1/job-search-project/scripts/setup-ssl-staging.sh --wildcard

# Or for individual certificates
sudo /home/deploy/staging-1/job-search-project/scripts/setup-ssl-staging.sh
```

### 10.5 Update Nginx Config with SSL Paths

After obtaining certificates, update the Nginx config if needed:

```bash
# Edit the nginx config
sudo nano /etc/nginx/sites-available/staging-multi

# Update the ssl_certificate paths to match your certificate location

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

### 10.6 Verify HTTPS

```bash
# Test HTTPS
curl -I https://staging-1.justapply.net

# Should return HTTP/2 200 with HSTS header
```

## 11) Deployment Version Verification

### 11.1 Check Version via API

```bash
# Check version for a staging slot
curl https://staging-1.justapply.net/api/version
```

Expected response:

```json
{
    "environment": "staging",
    "slot": "1",
    "branch": "main",
    "commit_sha": "abc123def456...",
    "deployed_at": "2025-01-22T10:30:00Z"
}
```

### 11.2 Check Version via File

```bash
ssh deploy@134.122.35.239
cat /home/deploy/staging-1/version.json
```

## 12) Slot Management

### 12.1 Starting a Slot

```bash
cd /home/deploy/staging-N/job-search-project
source /home/deploy/staging-N/.env.staging-N
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-N up -d
```

### 12.2 Stopping a Slot

```bash
cd /home/deploy/staging-N/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-N down
```

### 12.3 Viewing Logs

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-N logs -f
```

### 12.4 Cleaning Up a Slot

```bash
# Stop containers
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-N down

# Remove volumes (optional, clears all data)
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-N down -v

# Update slot registry in staging-slots.md to mark as Available
```

## 13) Troubleshooting

### 13.1 Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-N logs

# Check environment variables are loaded
env | grep POSTGRES

# Verify database connectivity
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=require" -c "SELECT 1"
```

### 13.2 Database Connection Issues

1. Verify database firewall allows droplet IP
2. Check SSL mode is set to `require`
3. Verify database name matches slot number

### 13.3 Port Conflicts

```bash
# Check what's using a port
sudo lsof -i :5001

# List all running containers
docker ps -a
```

### 13.4 Nginx 502 Bad Gateway

1. Check if the target container is running
2. Verify the port mapping matches nginx upstream
3. Check container logs for errors
