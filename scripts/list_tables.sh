#!/bin/bash
# List database tables in staging

sg docker -c 'docker exec staging_1_airflow_scheduler python3 << PYEOF
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
cur.execute("""
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_schema IN ('\''raw'\'', '\''staging'\'', '\''marts'\'') 
    ORDER BY table_schema, table_name
""")
for row in cur.fetchall():
    print(f"{row[0]}.{row[1]}")
conn.close()
PYEOF'
