"""Test script for ChatGPT enrichment.

This script tests the ChatGPT enrichment service by:
1. Finding a job that needs enrichment
2. Calling ChatGPT API to enrich it
3. Verifying the results are stored in the database
"""

import os
import sys
from pathlib import Path

# Add services to path
services_path = Path(__file__).parent.parent / "services"
sys.path.insert(0, str(services_path))

from dotenv import load_dotenv
from enricher import ChatGPTEnricher
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


def main():
    """Test ChatGPT enrichment."""
    print("=" * 60)
    print("ChatGPT Enrichment Test")
    print("=" * 60)

    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable is not set")
        print("   Please set OPENAI_API_KEY in your .env file or environment")
        return 1

    print(f"✅ OpenAI API key found: {api_key[:10]}...")

    # Build database connection
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)

    # Initialize ChatGPT enricher
    try:
        enricher = ChatGPTEnricher(
            database=database,
            api_key=api_key,
            model=os.getenv("CHATGPT_MODEL", "gpt-5-nano"),
            batch_size=1,  # Test with 1 job
        )
        print("✅ ChatGPT enricher initialized")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize ChatGPT enricher: {e}")
        return 1

    # Get jobs that need enrichment
    print("\n📋 Finding jobs that need ChatGPT enrichment...")
    jobs = enricher.get_jobs_to_enrich(limit=1)

    if not jobs:
        print("⚠️  No jobs found that need ChatGPT enrichment")
        print("   All jobs may already be enriched, or there are no jobs in the database")
        return 0

    job = jobs[0]
    print("✅ Found job to enrich:")
    print(f"   Job ID: {job.get('jsearch_job_id')}")
    print(f"   Title: {job.get('job_title')}")
    print(f"   Company: {job.get('employer_name')}")

    # Enrich the job
    print("\n🤖 Calling ChatGPT API to enrich job...")
    try:
        enrichment_data = enricher.enrich_job(job)

        print("✅ ChatGPT enrichment completed:")
        print(f"   Summary: {enrichment_data.get('job_summary', 'N/A')[:100]}...")
        print(f"   Skills: {enrichment_data.get('chatgpt_extracted_skills', [])}")
        print(f"   Location: {enrichment_data.get('chatgpt_extracted_location', 'N/A')}")

        # Update database
        print("\n💾 Updating database...")
        enricher.update_job_enrichment(
            job_key=job["jsearch_job_postings_key"],
            job_summary=enrichment_data["job_summary"],
            chatgpt_extracted_skills=enrichment_data["chatgpt_extracted_skills"],
            chatgpt_extracted_location=enrichment_data["chatgpt_extracted_location"],
        )
        print("✅ Database updated successfully")

        # Verify the update
        print("\n🔍 Verifying database update...")
        with database.get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    job_summary,
                    chatgpt_extracted_skills,
                    chatgpt_extracted_location,
                    chatgpt_enriched_at
                FROM staging.jsearch_job_postings
                WHERE jsearch_job_postings_key = %s
                """,
                (job["jsearch_job_postings_key"],),
            )
            result = cur.fetchone()
            if result:
                print("✅ Verification successful:")
                print(f"   Summary stored: {bool(result[0])}")
                print(f"   Skills stored: {bool(result[1])}")
                print(f"   Location stored: {bool(result[2])}")
                print(f"   Enriched at: {result[3]}")
            else:
                print("❌ ERROR: Could not find updated job in database")
                return 1

        print("\n" + "=" * 60)
        print("✅ ChatGPT enrichment test PASSED!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ ERROR: ChatGPT enrichment failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())




