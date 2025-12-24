"""
Migration script to add currency column to marts.profile_preferences table.

This script adds the currency column to existing databases that were created
before the currency feature was added.

Usage:
    python scripts/add_currency_to_profiles.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add services to path
services_path = Path(__file__).parent.parent / "services"
sys.path.insert(0, str(services_path))

from shared import PostgreSQLDatabase

# Load environment variables
load_dotenv()


def build_db_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def add_currency_column():
    """Add currency column to marts.profile_preferences table if it doesn't exist."""
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)

    print("Adding currency column to marts.profile_preferences...")

    with database.get_cursor() as cur:
        # Check if column already exists
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'marts'
              AND table_name = 'profile_preferences'
              AND column_name = 'currency'
        """)

        if cur.fetchone():
            print("✓ Currency column already exists. No migration needed.")
            return

        # Add the column
        cur.execute("""
            ALTER TABLE marts.profile_preferences
            ADD COLUMN currency varchar(3)
        """)

        print("✓ Currency column added successfully!")

        # Verify the column was added
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'marts'
              AND table_name = 'profile_preferences'
              AND column_name = 'currency'
        """)

        result = cur.fetchone()
        if result:
            print(f"✓ Verified: currency column exists (type: {result[1]})")
        else:
            print("✗ Warning: Column was not found after creation")


if __name__ == "__main__":
    try:
        add_currency_column()
        print("\nMigration completed successfully!")
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)

