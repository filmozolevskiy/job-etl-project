FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    git \
    postgresql-client \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install dbt-postgres (needed for dbt transformations)
RUN pip install --no-cache-dir dbt-core==1.7.0 dbt-postgres==1.7.0

# Download spaCy English model (needed for job enrichment)
RUN python -m spacy download en_core_web_sm

# Copy project files (this will be done by Cloud Agents, but we set up the structure)
# The actual code will be mounted/available in the workspace

# Set environment variables
ENV PYTHONPATH=/workspace
ENV PYTHONUNBUFFERED=1

# Default command (Cloud Agents will override this)
CMD ["/bin/bash"]
