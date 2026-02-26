#!/usr/bin/env python3
"""
Initialize staging database(s) with all migration scripts.

This script runs all SQL migration files from docker/init/ in proper order
to ensure the database schema is fully set up. It supports multiple slots.

Usage:
    python scripts/init_staging_db.py <slot_number> [slot_number ...]

    # Or with environment variables already set (single database):
    python scripts/init_staging_db.py

Example:
    python scripts/init_staging_db.py 1
    python scripts/init_staging_db.py 1 2 3
"""

import glob
import os
import sys

import psycopg2


def get_connection_params(slot: int | None = None) -> dict:
    """Get database connection parameters from environment or for a specific slot."""
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "25060")
    user = os.getenv("POSTGRES_USER", "doadmin")
    password = os.getenv("POSTGRES_PASSWORD")

    if slot:
        database = f"job_search_staging_{slot}"
    else:
        database = os.getenv("POSTGRES_DB")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "dbname": database,
        "sslmode": "require",
    }


def run_migration(conn, script_path: str) -> bool:
    """Run a single migration script."""
    script_name = os.path.basename(script_path)
    print(f"    Running {script_name}...", end=" ", flush=True)

    try:
        with open(script_path) as f:
            sql = f.read()

        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        cur.close()
        print("OK")
        return True
    except psycopg2.Error as e:
        # Check if error is due to already existing objects (which is OK)
        error_msg = str(e)
        if "already exists" in error_msg.lower():
            print("SKIPPED (already exists)")
            conn.rollback()
            return True
        else:
            print(f"FAILED: {e}")
            conn.rollback()
            return False


def get_migration_scripts(base_dir: str) -> list:
    """Get all migration scripts in proper order."""
    init_dir = os.path.join(base_dir, "docker", "init")
    scripts = glob.glob(os.path.join(init_dir, "*.sql"))

    # Sort by numeric prefix
    def sort_key(path):
        name = os.path.basename(path)
        # Extract numeric prefix (e.g., "01" from "01_create_schemas.sql")
        prefix = name.split("_")[0]
        try:
            return int(prefix)
        except ValueError:
            return 999  # Put non-numeric files at the end

    return sorted(scripts, key=sort_key)


def verify_schema(conn) -> dict:
    """Verify the database schema is properly set up."""
    cur = conn.cursor()

    # Check schemas
    cur.execute("""
        SELECT schema_name FROM information_schema.schemata
        WHERE schema_name IN ('raw', 'staging', 'marts')
        ORDER BY schema_name
    """)
    schemas = [row[0] for row in cur.fetchall()]

    # Check key tables
    cur.execute("""
        SELECT table_schema || '.' || table_name
        FROM information_schema.tables
        WHERE table_schema IN ('raw', 'staging', 'marts')
        ORDER BY table_schema, table_name
    """)
    tables = [row[0] for row in cur.fetchall()]

    cur.close()
    return {"schemas": schemas, "tables": tables}


def init_database(params: dict, scripts: list) -> bool:
    """Initialize a single database."""
    db_name = params["dbname"]
    print(f"--- Initializing database: {db_name} ---")
    print(f"Host: {params['host']}:{params['port']}")

    # Connect to database
    try:
        conn = psycopg2.connect(**params)
    except psycopg2.Error as e:
        print(f"Error connecting to database {db_name}: {e}")
        return False

    success_count = 0
    failed_count = 0

    for script in scripts:
        if run_migration(conn, script):
            success_count += 1
        else:
            failed_count += 1

    print(f"Completed: {success_count} succeeded, {failed_count} failed")

    # Verify schema
    print("Verifying schema...")
    result = verify_schema(conn)
    print(f"  Schemas: {', '.join(result['schemas'])}")
    print(f"  Tables: {len(result['tables'])} total")

    # Check for key tables
    key_tables = [
        "raw.jsearch_job_postings",
        "staging.jsearch_job_postings",
        "staging.chatgpt_enrichments",
        "marts.dim_companies",
        "marts.dim_ranking",
        "marts.users",
    ]

    missing = [t for t in key_tables if t not in result["tables"]]
    if missing:
        print(f"  WARNING: Missing key tables: {', '.join(missing)}")
    else:
        print("  All key tables present")

    conn.close()
    return failed_count == 0


def main():
    # Determine base directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)

    # Get migration scripts
    scripts = get_migration_scripts(base_dir)
    if not scripts:
        print("Error: No migration scripts found in docker/init/")
        sys.exit(1)

    print(f"Found {len(scripts)} migration scripts")

    # Get slot numbers from arguments
    slots = []
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            try:
                slot = int(arg)
                if not 1 <= slot <= 10:
                    print(f"Error: Slot number {arg} must be between 1 and 10")
                    sys.exit(1)
                slots.append(slot)
            except ValueError:
                print(f"Error: Invalid slot number: {arg}")
                sys.exit(1)
    else:
        # Use None to indicate using env vars directly
        slots = [None]

    overall_success = True
    for slot in slots:
        params = get_connection_params(slot)
        if not params["host"] or not params["password"]:
            print(f"Error: Database connection parameters not set for slot {slot or 'default'}.")
            print("Set POSTGRES_HOST, POSTGRES_PASSWORD, etc. environment variables.")
            overall_success = False
            continue

        if not init_database(params, scripts):
            overall_success = False

    if not overall_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
