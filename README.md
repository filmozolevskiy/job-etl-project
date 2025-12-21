# Job Postings Data Platform

A data engineering project for extracting, transforming, and ranking job postings from multiple sources, with daily email notifications and BI integration.

## Overview

This platform implements a **Medallion architecture** (Bronze/Silver/Gold) on PostgreSQL to:
- Extract job postings from the JSearch API
- Enrich employer data with Glassdoor company information
- Normalize and transform data using dbt
- Rank jobs based on user-defined profiles
- Send daily email summaries of top-ranked jobs
- Expose data to Tableau for analytics

## Project Structure

```
.
├── services/              # Python services (extractor, enricher, ranker, notifier)
├── dbt/                   # dbt project for transformations
├── airflow/               # Airflow DAGs and configuration
│   ├── dags/
│   └── plugins/
├── profile_ui/           # Profile management web interface
├── tests/                # Test files
├── docker/               # Dockerfiles and initialization scripts
│   └── init/            # Database initialization scripts
└── Project Documentation/  # Project documentation and PRDs
```

## Technologies

- **Language**: Python 3.11+
- **Database**: PostgreSQL (Medallion: `raw`, `staging`, `marts` schemas)
- **Transformations**: dbt
- **Orchestration**: Apache Airflow
- **Containerization**: Docker / Docker Compose
- **Testing**: pytest
- **Linting/Formatting**: ruff

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- dbt-core and dbt-postgres
- spaCy English model (for job enrichment):
  ```bash
  python -m spacy download en_core_web_sm
  ```

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "Job Search Project"
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Start the local stack**
   ```bash
   docker-compose up -d
   ```

4. **Install spaCy model** (required for job enrichment)
   ```bash
   python -m spacy download en_core_web_sm
   ```

5. **Initialize dbt project** (if not already initialized)
   ```bash
   cd dbt
   dbt debug
   dbt run
   ```
   
   **Note**: If the staging table already exists, run the migration script to add enrichment columns:
   ```bash
   psql -h localhost -U postgres -d job_search_db -f scripts/add_enrichment_columns.sql
   ```

6. **Access services**
   - Airflow UI: http://localhost:8080 (admin/admin)
   - Profile UI: http://localhost:5000 (if enabled)
   - PostgreSQL: localhost:5432

