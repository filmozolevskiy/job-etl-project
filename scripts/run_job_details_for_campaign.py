#!/usr/bin/env python3
"""
Run JSearch job-details for all jobs in a campaign (e.g. from production).

Use this to see what the API returns for each job and how we interpret
listing_available (not relevant = empty data).

Usage:
  # Load prod DB + JSearch from .env.production
  ENVIRONMENT=production python scripts/run_job_details_for_campaign.py "BI Developer - Canada"

  # Or set POSTGRES_* and JSEARCH_API_KEY yourself
  python scripts/run_job_details_for_campaign.py "BI Developer - Canada"

Requires: POSTGRES_*, JSEARCH_API_KEY; python deps: psycopg2-binary, requests, python-dotenv.
Run from project venv: source .venv/bin/activate (or pip install -r requirements.txt), then
  ENVIRONMENT=production python scripts/run_job_details_for_campaign.py "BI Developer - Canada"
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Load env from repo root
repo_root = Path(__file__).resolve().parents[1]
env_name = os.getenv("ENVIRONMENT", "development")
env_file = repo_root / f".env.{env_name}"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)
else:
    env_path = repo_root / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)

import psycopg2
import requests

JSEARCH_BASE = "https://api.openwebninja.com/jsearch"
RATE_LIMIT_DELAY = 1.0


def get_job_details(api_key: str, job_id: str) -> dict:
    """Call JSearch job-details API. Returns parsed JSON or raises."""
    url = f"{JSEARCH_BASE}/job-details"
    headers = {"x-api-key": api_key}
    resp = requests.get(url, headers=headers, params={"job_id": job_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: run_job_details_for_campaign.py <campaign_name>", file=sys.stderr)
        print('Example: run_job_details_for_campaign.py "BI Developer - Canada"', file=sys.stderr)
        sys.exit(1)

    campaign_name = sys.argv[1].strip()
    api_key = os.getenv("JSEARCH_API_KEY")
    if not api_key:
        print("JSEARCH_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "job_search_db")
    sslmode = os.getenv("POSTGRES_SSL_MODE", "prefer")
    conn = psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=dbname,
        connect_timeout=10, sslmode=sslmode,
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT campaign_id FROM marts.job_campaigns WHERE campaign_name = %s",
                (campaign_name,),
            )
            row = cur.fetchone()
            if not row:
                print(f"Campaign not found: {campaign_name!r}", file=sys.stderr)
                sys.exit(1)
            campaign_id = row[0]
            print(f"Campaign: {campaign_name!r} (campaign_id={campaign_id})")

            try:
                limit = int(os.getenv("JOB_DETAILS_LIMIT", "0"))
            except ValueError:
                limit = 0
            limit = limit if limit > 0 else None
            from_end = os.getenv("JOB_DETAILS_FROM_END", "").strip().lower() in ("1", "true", "yes")
            order = "ORDER BY fj.jsearch_job_id DESC" if from_end else "ORDER BY fj.jsearch_job_id"
            cur.execute(
                f"""
                SELECT fj.jsearch_job_id, fj.job_title
                FROM marts.fact_jobs fj
                WHERE fj.campaign_id = %s
                {order}
                """ + (" LIMIT %s" if limit else ""),
                (campaign_id, limit) if limit else (campaign_id,),
            )
            jobs = cur.fetchall()
    finally:
        conn.close()

    if not jobs:
        print("No jobs in fact_jobs for this campaign.")
        return

    print(f"Found {len(jobs)} job(s). Calling job-details for each (rate-limited).\n")

    for jsearch_job_id, job_title in jobs:
        title_short = (job_title or "N/A")[:50]
        time.sleep(RATE_LIMIT_DELAY)
        try:
            response = get_job_details(api_key, jsearch_job_id)
            status = response.get("status", "?")
            data = response.get("data")
            if data is None:
                listing_available = "unknown (no 'data' key)"
            elif isinstance(data, list):
                listing_available = "yes" if data else "NO (not relevant – empty data)"
            else:
                listing_available = "yes" if data else "no"
            data_len = len(data) if isinstance(data, list) else "N/A"
            print(f"  {jsearch_job_id}")
            print(f"    title: {title_short}")
            print(f"    status={status!r}  data length={data_len}  listing_available={listing_available}")
        except requests.RequestException as e:
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code is not None and status_code >= 500:
                listing_available = "NO (not relevant – 5xx)"
            else:
                listing_available = f"ERROR: {e}"
            print(f"  {jsearch_job_id}")
            print(f"    title: {title_short}")
            print(f"    {listing_available}")
        print()

    print("Done.")


if __name__ == "__main__":
    main()
