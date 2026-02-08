#!/usr/bin/env python3
"""List users in marts.users (Campaign UI accounts). Reads POSTGRES_* from env."""

import os
import sys
from pathlib import Path

# Optional: load .env from project root (development/staging)
try:
    from dotenv import load_dotenv
    repo_root = Path(__file__).resolve().parents[1]
    env_name = os.getenv("ENVIRONMENT", "development")
    env_file = repo_root / f".env.{env_name}"
    if env_file.exists():
        load_dotenv(env_file)
    elif (repo_root / ".env").exists():
        load_dotenv(repo_root / ".env")
except ImportError:
    pass

import psycopg2

def main() -> None:
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    dbname = os.getenv("POSTGRES_DB")
    sslmode = os.getenv("POSTGRES_SSL_MODE", "prefer")

    if not all([host, port, user, dbname]):
        print("Set POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_DB (and POSTGRES_PASSWORD).", file=sys.stderr)
        sys.exit(1)

    try:
        conn = psycopg2.connect(
            host=host,
            port=int(port),
            user=user,
            password=password or "",
            dbname=dbname,
            sslmode="require" if sslmode == "require" else "prefer",
        )
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id, username, email, role, created_at, last_login
        FROM marts.users
        ORDER BY user_id
        """
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("No users in marts.users.")
        return

    print(f"{'user_id':<8} {'username':<20} {'email':<35} {'role':<6} {'created_at':<22} {'last_login'}")
    print("-" * 110)
    for r in rows:
        uid, username, email, role, created, last_login = r
        created_s = created.strftime("%Y-%m-%d %H:%M") if created else ""
        last_s = last_login.strftime("%Y-%m-%d %H:%M") if last_login else ""
        print(f"{uid:<8} {(username or '')[:19]:<20} {(email or '')[:34]:<35} {(role or '')[:5]:<6} {created_s:<22} {last_s}")
    print(f"\nTotal: {len(rows)} user(s)")


if __name__ == "__main__":
    main()
