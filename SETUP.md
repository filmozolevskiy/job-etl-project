# Setup Guide

This guide will help you set up the Job Search Platform for local development.

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- Python 3.11+ (for local development)
- Git

## Initial Setup

### 1. Environment Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=job_search_db
POSTGRES_PORT=5432
POSTGRES_HOST=localhost

# API Keys
JSEARCH_API_KEY=YOUR_JSEARCH_API_KEY
GLASSDOOR_API_KEY=YOUR_GLASSDOOR_API_KEY

# Email/SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
SMTP_FROM_EMAIL=your_email@gmail.com

# Airflow Configuration
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin
AIRFLOW_WEBSERVER_PORT=8080
AIRFLOW_UID=50000

# Profile UI Configuration
PROFILE_UI_PORT=5000
FLASK_ENV=development
FLASK_DEBUG=1

# Timezone
TZ=America/Toronto
```

### 2. Start Docker Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Verify Database Schemas

Connect to PostgreSQL and verify schemas were created:

```bash
docker exec -it job_search_postgres psql -U postgres -d job_search_db

# In psql:
\dn  # List schemas (should show raw, staging, marts)
\q   # Exit
```

### 4. Set Up Python Environment (for local development)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 5. Configure dbt

The dbt project is already configured in `dbt/`. Test the connection:

```bash
cd dbt
dbt debug
```

If successful, you should see:
- Connection test: PASS
- Profile configuration: VALID

### 6. Access Services

Once containers are running:

- **Airflow UI**: http://localhost:8080
  - Username: `admin` (or your AIRFLOW_USERNAME)
  - Password: `admin` (or your AIRFLOW_PASSWORD)
  
- **Profile UI**: http://localhost:5000 (when implemented)

- **PostgreSQL**: localhost:5432
  - Database: `job_search_db`
  - User: `postgres`
  - Password: (from .env)

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=services --cov-report=html
```

### Linting and Formatting

```bash
# Check for linting issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### dbt Development

```bash
cd dbt

# Run all models
dbt run

# Run specific model
dbt run --select staging.jsearch_job_postings

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve
```

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL container is running: `docker-compose ps`
- Check database logs: `docker-compose logs postgres`
- Verify environment variables in `.env`

### Airflow Issues

- Check Airflow logs: `docker-compose logs airflow-webserver`
- Ensure Airflow init completed: `docker-compose logs airflow-init`
- Reset Airflow database: `docker-compose down -v` (WARNING: deletes data)

### dbt Connection Issues

- Verify `dbt/profiles.yml` uses correct environment variables
- Test connection: `dbt debug`
- Ensure PostgreSQL is accessible from your host

## Next Steps

1. Implement Phase 2 tasks (see `Project Documentation/implementation-todo.md`)
2. Create first dbt models for raw layer
3. Implement source extractor service
4. Test end-to-end pipeline

