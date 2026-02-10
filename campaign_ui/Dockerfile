# Multi-stage build for React frontend and Python backend

# Stage 1: Build React frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build React app
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy services directory first (for imports)
COPY services /app/services

# Copy campaign_ui requirements and install
COPY campaign_ui/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy campaign_ui application code
COPY campaign_ui/app.py /app/app.py
COPY campaign_ui/templates /app/templates

# Copy built React app from frontend-builder stage
COPY --from=frontend-builder /app/frontend/dist /frontend/dist

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
