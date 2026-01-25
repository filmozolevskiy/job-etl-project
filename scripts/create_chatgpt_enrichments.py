#!/usr/bin/env python3
"""Create the staging.chatgpt_enrichments table."""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=os.getenv("POSTGRES_PORT"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    dbname=os.getenv("POSTGRES_DB"),
    sslmode="require"
)
cur = conn.cursor()

# Create staging.chatgpt_enrichments table
sql = """
CREATE TABLE IF NOT EXISTS staging.chatgpt_enrichments (
    chatgpt_enrichment_key BIGSERIAL PRIMARY KEY,
    jsearch_job_postings_key BIGINT NOT NULL,
    job_summary TEXT,
    chatgpt_extracted_skills JSONB,
    chatgpt_extracted_location VARCHAR(255),
    chatgpt_seniority_level VARCHAR(50),
    chatgpt_remote_work_type VARCHAR(50),
    chatgpt_job_min_salary NUMERIC,
    chatgpt_job_max_salary NUMERIC,
    chatgpt_salary_period VARCHAR(50),
    chatgpt_salary_currency VARCHAR(10),
    chatgpt_enriched_at TIMESTAMP,
    chatgpt_enrichment_status JSONB,
    dwh_load_date DATE DEFAULT CURRENT_DATE,
    dwh_load_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chatgpt_enrichments_job_postings 
        FOREIGN KEY (jsearch_job_postings_key) 
        REFERENCES staging.jsearch_job_postings(jsearch_job_postings_key),
    CONSTRAINT uq_chatgpt_enrichments_job_postings_key 
        UNIQUE (jsearch_job_postings_key)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_chatgpt_enrichments_job_postings_key 
    ON staging.chatgpt_enrichments(jsearch_job_postings_key);
CREATE INDEX IF NOT EXISTS idx_chatgpt_enrichments_enriched_at 
    ON staging.chatgpt_enrichments(chatgpt_enriched_at);
"""

try:
    cur.execute(sql)
    conn.commit()
    print("Successfully created staging.chatgpt_enrichments table")
except Exception as e:
    print(f"Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
