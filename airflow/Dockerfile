FROM apache/airflow:2.8.0

# Switch to root to install system dependencies
USER root

# Install system dependencies required for dbt-postgres and spaCy
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    git \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Switch back to airflow user for pip installs
USER airflow

# Install dbt-core and dbt-postgres using airflow user's pip
RUN pip install --no-cache-dir \
    dbt-core==1.7.0 \
    dbt-postgres==1.7.0

# Install Python dependencies required by services
# These are needed for the extractor services to run in Airflow tasks
# Note: spaCy 3.6.x is used for Python 3.8 compatibility (Airflow 2.8.0 uses Python 3.8)
RUN pip install --no-cache-dir \
    psycopg2-binary>=2.9.9 \
    requests>=2.31.0 \
    python-dotenv>=1.0.0 \
    rapidfuzz>=3.0.0 \
    "spacy>=3.6.0,<3.7.0" \
    openai>=1.0.0

# Download spaCy English model for NLP enrichment
RUN python -m spacy download en_core_web_sm

