#!/usr/bin/env python3
"""Create the staging.chatgpt_enrichments table with proper constraints."""
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

# First check if jsearch_job_postings_key has a unique constraint or is primary key
cur.execute("""
    SELECT 
        tc.constraint_type, 
        tc.constraint_name,
        kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.table_schema = 'staging' 
    AND tc.table_name = 'jsearch_job_postings'
    AND kcu.column_name = 'jsearch_job_postings_key'
""")
constraints = cur.fetchall()
print(f"Existing constraints on jsearch_job_postings_key: {constraints}")

# Check if chatgpt_enrichments already exists
cur.execute("""
    SELECT EXISTS(
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'staging' 
        AND table_name = 'chatgpt_enrichments'
    )
""")
exists = cur.fetchone()[0]
print(f"chatgpt_enrichments table exists: {exists}")

if not exists:
    # Create table without foreign key constraint initially
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
        print(f"Error creating table: {e}")
        conn.rollback()
else:
    print("Table already exists, skipping creation")

cur.close()
conn.close()
