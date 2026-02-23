# Environment Configuration Management

This document describes how environment-specific configuration files are managed for the Job Search Assistant project.

## Overview

The project supports three environments:
- **development**: Local development environment
- **staging**: Staging environment for testing before production
- **production**: Production environment

Each environment has its own `.env.{environment}` file containing environment-specific configuration values.

## Environment Files

### `.env.example`
Template file documenting all available environment variables. This file is committed to version control and serves as documentation.

### `.env.development`
Local development configuration. This file is **git-ignored** and should contain your local development values. Copy from `.env.example` and fill in your actual values.

### `.env.staging` and `.env.production`
Template files for staging and production environments. Actual files with secrets should **never** be committed to version control. Store actual values securely on the server or in DigitalOcean App Platform secrets.

## Setting the Environment

The environment is selected using the `ENVIRONMENT` environment variable:

```bash
# Development (default)
export ENVIRONMENT=development

# Staging
export ENVIRONMENT=staging

# Production
export ENVIRONMENT=production
```

## Loading Environment Variables

### Docker Compose

Docker Compose automatically loads environment-specific files based on the `ENVIRONMENT` variable:

```bash
# Default to development
docker-compose up

# Use staging environment
ENVIRONMENT=staging docker-compose up

# Use production environment
ENVIRONMENT=production docker-compose up
```

The `docker-compose.yml` file is configured to load `.env.{ENVIRONMENT}` first, falling back to `.env` if the environment-specific file doesn't exist.

### Local Development (Python)

When running services locally (outside Docker), the Python code automatically loads environment-specific files:

- **campaign_ui/app.py**: Loads `.env.{ENVIRONMENT}` from the project root
- **airflow/dags/task_functions.py**: Loads `.env.{ENVIRONMENT}` from the project root (in Docker, uses `/opt/airflow`)

Set the `ENVIRONMENT` variable before running:

```bash
export ENVIRONMENT=development
python campaign_ui/app.py
```

### Using the Helper Script

Use the `scripts/load_env.sh` helper script to load environment variables:

```bash
# Load development environment (default)
source scripts/load_env.sh

# Load staging environment
source scripts/load_env.sh staging

# Load production environment
source scripts/load_env.sh production
```

## Environment Variables

### Database Configuration

- `POSTGRES_HOST`: Database host
  - Development: `localhost`
  - Staging/Production: DigitalOcean Managed PostgreSQL host
- `POSTGRES_PORT`: Database port
  - Development: `5432`
  - Staging/Production: `25060` (DigitalOcean connection pooler)
- `POSTGRES_USER`: Database username
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_DB`: Database name

### Flask Configuration

- `FLASK_ENV`: Flask environment (`development` or `production`)
- `FLASK_DEBUG`: Debug mode (`1` or `0`)
- `FLASK_SECRET_KEY`: Flask session secret key (must be unique per environment)
- `JWT_SECRET_KEY`: JWT token secret key (must be unique per environment)

### Airflow Configuration

- `AIRFLOW_USERNAME`: Airflow web UI username
- `AIRFLOW_PASSWORD`: Airflow web UI password
- `AIRFLOW_WEBSERVER_PORT`: Airflow web UI port (default: `8080`)
- `AIRFLOW_UID`: Airflow user ID (default: `50000`)
- `AIRFLOW_FERNET_KEY`: Fernet key for Airflow encryption

### API Keys

- `JSEARCH_API_KEY`: JSearch API key
- `GLASSDOOR_API_KEY`: Glassdoor API key
- `OPENAI_API_KEY`: OpenAI API key for ChatGPT enrichment

### SMTP Configuration

- `SMTP_HOST`: SMTP server hostname
- `SMTP_PORT`: SMTP server port (default: `587`; use `2525` for SendGrid on restricted networks)
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `SMTP_FROM_EMAIL`: Email address for sender (required for SendGrid: use a verified Single Sender address)

**SendGrid (e.g. on DigitalOcean where 587 is blocked):** Set `SMTP_HOST=smtp.sendgrid.net`, `SMTP_PORT=2525`, `SMTP_USER=apikey`, `SMTP_PASSWORD=<API key>`, and `SMTP_FROM_EMAIL` to a verified sender. See [SendGrid SMTP](https://docs.sendgrid.com/for-developers/sending-email/getting-started-smtp).

## Secret Management

### Local Development

1. Copy `.env.example` to `.env.development`
2. Fill in your local development values
3. The `.env.development` file is git-ignored and will not be committed

### Staging and Production

**Never commit actual `.env.staging` or `.env.production` files with secrets to version control.**

#### Option 1: DigitalOcean App Platform Secrets

If using DigitalOcean App Platform:
1. Add secrets via the DigitalOcean console
2. Secrets are automatically injected as environment variables
3. No `.env` files needed on the server

#### Option 2: Server-Based `.env` Files

If deploying to a DigitalOcean Droplet:
1. Create `.env.staging` or `.env.production` on the server
2. Store files securely with restricted permissions:
   ```bash
   chmod 600 .env.staging
   chmod 600 .env.production
   ```
3. Ensure files are not committed to git (already in `.gitignore`)

### Generating Secure Keys

#### Flask Secret Keys

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Fernet Key (Airflow)

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Best Practices

1. **Use different secrets per environment**: Never reuse production secrets in staging or development
2. **Rotate secrets regularly**: Update secrets periodically, especially after team member changes
3. **Document all variables**: Ensure `.env.example` is kept up-to-date with all required variables
4. **Validate before deployment**: Verify all required variables are set before deploying to staging or production
5. **Use strong passwords**: Generate secure random values for all secret keys
6. **Restrict file permissions**: On servers, use `chmod 600` for `.env` files

## Troubleshooting

### Environment variables not loading

1. Check that `ENVIRONMENT` is set correctly:
   ```bash
   echo $ENVIRONMENT
   ```
2. Verify the `.env.{ENVIRONMENT}` file exists
3. Check file permissions and accessibility
4. For Docker Compose, ensure `ENVIRONMENT` is exported before running `docker-compose`

### Services using wrong environment

- Ensure `ENVIRONMENT` is set before starting services
- For Docker Compose, explicitly set: `ENVIRONMENT=staging docker-compose up`
- Check that the correct `.env.{ENVIRONMENT}` file exists and contains expected values
