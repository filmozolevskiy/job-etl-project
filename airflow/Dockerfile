FROM apache/airflow:2.8.0

# Switch to root to install system dependencies
USER root

# Install system dependencies required for dbt-postgres
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    git \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Switch back to airflow user for pip installs
USER airflow

# Install dbt-core and dbt-postgres using airflow user's pip
RUN pip install --no-cache-dir \
    dbt-core==1.7.0 \
    dbt-postgres==1.7.0

