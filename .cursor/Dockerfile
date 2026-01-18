FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    git \
    postgresql-client \
    sudo \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install Python dependencies
# Note: Cursor handles mounting the codebase, so requirements.txt will be available at runtime
# We install the core dependencies here, and can install from requirements.txt in install step
RUN pip install --no-cache-dir \
    psycopg2-binary>=2.9.9 \
    requests>=2.31.0 \
    python-dotenv>=1.0.0 \
    sqlalchemy>=2.0.0 \
    pandas>=2.1.0 \
    "spacy>=3.6.0,<3.7.0" \
    rapidfuzz>=3.0.0 \
    bcrypt>=4.0.0 \
    openai>=1.0.0 \
    PyPDF2>=3.0.0 \
    python-docx>=1.1.0 \
    pytest>=7.4.0 \
    pytest-cov>=4.1.0 \
    pytest-mock>=3.12.0 \
    ruff>=0.1.0 \
    PyGithub>=2.1.0 \
    dbt-core==1.7.0 \
    dbt-postgres==1.7.0

# Download spaCy English model (needed for job enrichment)
RUN python -m spacy download en_core_web_sm

# Set environment variables
ENV PYTHONPATH=/workspace
ENV PYTHONUNBUFFERED=1

# Default command (Cloud Agents will override this)
CMD ["/bin/bash"]
