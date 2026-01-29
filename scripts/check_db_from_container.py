import os
import sys

import psycopg2

h = os.environ.get("POSTGRES_HOST")
p = os.environ.get("POSTGRES_PORT")
u = os.environ.get("POSTGRES_USER")
pw = os.environ.get("POSTGRES_PASSWORD")
db = os.environ.get("POSTGRES_DB")
print("Connecting to", h, p, db, flush=True)
try:
    c = psycopg2.connect(host=h, port=int(p), user=u, password=pw, dbname=db, sslmode="require")
    cur = c.cursor()
    cur.execute("SELECT schema_name FROM information_schema.schemata")
    print("Schemas:", [r[0] for r in cur.fetchall()])
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='raw'")
    print("raw tables:", [r[0] for r in cur.fetchall()])
    cur.execute("SELECT 1 FROM raw.jsearch_job_postings LIMIT 1")
    print("raw.jsearch_job_postings: OK")
    c.close()
    print("DB OK")
except Exception as e:
    print("Error:", e, file=sys.stderr)
    sys.exit(1)
