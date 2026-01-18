FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    git \
    postgresql-client \
    curl \
    ca-certificates \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Install numpy with a specific compatible version first to avoid binary incompatibility
# This must be done before installing spacy/thinc to ensure compatibility
RUN pip install --no-cache-dir "numpy==1.24.3"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install dbt-postgres (needed for dbt transformations)
RUN pip install --no-cache-dir dbt-core==1.7.0 dbt-postgres==1.7.0

# Reinstall numpy after spacy to ensure binary compatibility
# This ensures thinc (spacy's dependency) uses the correct numpy version
RUN pip install --no-cache-dir --force-reinstall "numpy==1.24.3"

# Note: spaCy model download moved to install step in environment.json
# This avoids build failures and allows the model to be downloaded during agent setup

# Copy project files (this will be done by Cloud Agents, but we set up the structure)
# The actual code will be mounted/available in the workspace

# Set environment variables
ENV PYTHONPATH=/workspace
ENV PYTHONUNBUFFERED=1

# Default command (Cloud Agents will override this)
CMD ["/bin/bash"]
