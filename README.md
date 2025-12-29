# Job Postings Data Platform

A data engineering project for extracting, transforming, and ranking job postings from multiple sources, with daily email notifications and BI integration.

## Overview

This platform implements a **Medallion architecture** (Bronze/Silver/Gold) on PostgreSQL to:
- Extract job postings from the JSearch API
- Enrich employer data with Glassdoor company information
- Normalize and transform data using dbt
- Rank jobs based on user-defined campaigns
- Send daily email summaries of top-ranked jobs
- Expose data to Tableau for analytics

## Project Structure

```
.
├── services/              # Python services (extractor, enricher, ranker, notifier)
│   ├── enricher/         # Job enrichment service
│   │   ├── job_enricher.py      # Main enrichment logic
│   │   ├── technical_skills.py  # Technical skills patterns
│   │   ├── seniority_patterns.py # Seniority level patterns
│   │   └── queries.py           # SQL queries
│   ├── extractor/         # Job extraction services
│   ├── ranker/           # Job ranking service
│   └── notifier/         # Notification services
├── dbt/                   # dbt project for transformations
├── airflow/               # Airflow DAGs and configuration
│   ├── dags/
│   └── plugins/
├── campaign_ui/           # Campaign management web interface
├── tests/                # Test files
├── docker/               # Dockerfiles and initialization scripts
│   └── init/            # Database initialization scripts
└── scripts/              # Utility scripts (migrations, etc.)
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
   cp env.template .env
   # Edit .env with your API keys and configuration
   # IMPORTANT: Set AIRFLOW_API_URL, AIRFLOW_API_USERNAME, AIRFLOW_API_PASSWORD for DAG triggering
   # IMPORTANT: Set FLASK_SECRET_KEY for session security
   ```

3. **Start the local stack**
   ```bash
   docker-compose up -d
   ```

4. **Install spaCy model** (required for job enrichment)
   ```bash
   docker exec -it job_search_airflow_webserver python -m spacy download en_core_web_sm
   ```
   
   **Note**: The spaCy model is also installed during Docker image build, but you can verify it's available with the command above.

5. **Initialize dbt project** (if not already initialized)
   ```bash
   docker exec -it job_search_airflow_webserver bash -c "cd /opt/airflow/dbt && dbt debug && dbt run"
   ```
   
   **Note**: The enrichment columns (`extracted_skills`, `seniority_level`) are automatically added to the staging table by dbt. If you're upgrading from an older version, the dbt model preserves existing enrichment data when recreating the table.

6. **Access services**
   - Airflow UI: http://localhost:8080 (admin/admin)
   - Campaign UI: http://localhost:5000 (if enabled)
   - PostgreSQL: localhost:5432

## Services

### Enricher Service

The enricher service (`services/enricher/`) enriches job postings with:
- **Technical Skills**: Extracted from job descriptions using pattern matching and NLP
- **Seniority Levels**: Identified from job titles (intern, junior, mid, senior, executive)

**Key Files:**
- `job_enricher.py`: Main enrichment logic using spaCy NLP
- `technical_skills.py`: Comprehensive set of technical skills patterns (100+ skills)
- `seniority_patterns.py`: Patterns for identifying seniority levels
- `queries.py`: SQL queries for fetching and updating enriched jobs

**Customization:**
To add new skills or seniority patterns, edit:
- `services/enricher/technical_skills.py` - Add skills to the `TECHNICAL_SKILLS` set
- `services/enricher/seniority_patterns.py` - Add patterns to the `SENIORITY_PATTERNS` dict

