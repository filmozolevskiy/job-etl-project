#!/bin/bash
# Test database connection from Airflow scheduler container

sg docker -c 'docker exec staging_1_airflow_scheduler python3 -c "
import os
import psycopg2

host = os.getenv(\"POSTGRES_HOST\")
port = os.getenv(\"POSTGRES_PORT\")
user = os.getenv(\"POSTGRES_USER\")
password = os.getenv(\"POSTGRES_PASSWORD\")
dbname = os.getenv(\"POSTGRES_DB\")

print(f\"Connecting to {host}:{port}/{dbname} as {user}\")

try:
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        sslmode=\"require\"
    )
    cur = conn.cursor()
    cur.execute(\"SELECT 1\")
    result = cur.fetchone()
    print(f\"Connection successful! Result: {result}\")
    
    # Check schemas
    cur.execute(\"SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN (\x27pg_catalog\x27, \x27information_schema\x27) ORDER BY schema_name\")
    schemas = cur.fetchall()
    print(f\"Schemas: {[s[0] for s in schemas]}\")
    
    conn.close()
except Exception as e:
    print(f\"Connection failed: {e}\")
"'
