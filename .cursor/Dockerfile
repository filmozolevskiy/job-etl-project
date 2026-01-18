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

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Install numpy with a specific compatible version first to avoid binary incompatibility
# This must be done before installing spacy/thinc to ensure compatibility
RUN pip install --no-cache-dir "numpy==1.24.3"

# Install Python dependencies
# Note: Cursor handles mounting the codebase, so requirements.txt will be available at runtime
# We install the core dependencies here, and can install from requirements.txt in install step
# Using spacy>=3.7.0 for Python 3.11 compatibility (requirements.txt specifies >=3.7.0)
RUN pip install --no-cache-dir \
    psycopg2-binary>=2.9.9 \
    requests>=2.31.0 \
    python-dotenv>=1.0.0 \
    sqlalchemy>=2.0.0 \
    pandas>=2.1.0 \
    "spacy>=3.7.0" \
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

# Reinstall numpy after spacy to ensure binary compatibility
# This ensures thinc (spacy's dependency) uses the correct numpy version
RUN pip install --no-cache-dir --force-reinstall "numpy==1.24.3"

# Note: spaCy model download moved to install step in environment.json
# This avoids build failures and allows the model to be downloaded during agent setup

# Set environment variables
ENV PYTHONPATH=/workspace
ENV PYTHONUNBUFFERED=1

# Default command (Cloud Agents will override this)
CMD ["/bin/bash"]
