"""
Create Profile and Extract Jobs

Script to create a job profile and immediately extract jobs for it.
Useful for testing and quick setup.
"""

import os
import sys
import logging
from datetime import datetime
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Handle both module and standalone script imports
try:
    from .job_extractor import JobExtractor
except ImportError:
    # If running as standalone script
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from services.extractor.job_extractor import JobExtractor

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def create_profile(
    db_connection_string: str,
    profile_name: str,
    query: str,
    country: str = "ca",
    location: str = None,
    date_window: str = "week",
    email: str = None,
    skills: str = None,
    min_salary: float = None,
    max_salary: float = None,
    remote_preference: str = None,
    seniority: str = None
) -> int:
    """
    Create a new profile in marts.profile_preferences.
    
    Args:
        db_connection_string: PostgreSQL connection string
        profile_name: Name for the profile
        query: Job search query
        country: Country code (default: "ca")
        location: Location string (optional)
        date_window: Date window for jobs (default: "week")
        email: Email for notifications (optional)
        skills: Preferred skills (optional)
        min_salary: Minimum salary (optional)
        max_salary: Maximum salary (optional)
        remote_preference: Remote work preference (optional)
        seniority: Preferred seniority level (optional)
        
    Returns:
        Profile ID of the created profile
    """
    conn = psycopg2.connect(db_connection_string)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    try:
        with conn.cursor() as cur:
            # Get next profile_id
            cur.execute("SELECT COALESCE(MAX(profile_id), 0) + 1 FROM marts.profile_preferences")
            profile_id = cur.fetchone()[0]
            
            # Insert new profile
            now = datetime.now()
            cur.execute("""
                INSERT INTO marts.profile_preferences (
                    profile_id,
                    profile_name,
                    is_active,
                    query,
                    location,
                    country,
                    date_window,
                    email,
                    skills,
                    min_salary,
                    max_salary,
                    remote_preference,
                    seniority,
                    created_at,
                    updated_at,
                    total_run_count,
                    last_run_at,
                    last_run_status,
                    last_run_job_count
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                profile_id,
                profile_name,
                True,  # is_active
                query,
                location,
                country.upper(),
                date_window,
                email,
                skills,
                min_salary,
                max_salary,
                remote_preference,
                seniority,
                now,  # created_at
                now,  # updated_at
                0,  # total_run_count
                None,  # last_run_at
                'never',  # last_run_status
                0  # last_run_job_count
            ))
            
            logger.info(f"Created profile {profile_id}: {profile_name}")
            return profile_id
            
    finally:
        conn.close()


def main():
    """Main entry point for creating a profile and extracting jobs."""
    import argparse
    
    # Print to stdout immediately to verify script is running
    print("Starting profile creation script...", flush=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    
    parser = argparse.ArgumentParser(description='Create a job profile and extract jobs')
    parser.add_argument('--profile-name', default='Business Intelligence Engineer',
                       help='Profile name')
    parser.add_argument('--query', default='Business Intelligence Engineer',
                       help='Job search query')
    parser.add_argument('--country', default='ca',
                       help='Country code (e.g., ca, us)')
    parser.add_argument('--location', default=None,
                       help='Location (optional)')
    parser.add_argument('--date-window', default='week',
                       help='Date window for jobs (today, week, month)')
    parser.add_argument('--email', default=None,
                       help='Email for notifications (optional)')
    parser.add_argument('--skills', default=None,
                       help='Preferred skills (optional)')
    parser.add_argument('--min-salary', type=float, default=None,
                       help='Minimum salary (optional)')
    parser.add_argument('--max-salary', type=float, default=None,
                       help='Maximum salary (optional)')
    parser.add_argument('--remote-preference', default=None,
                       help='Remote work preference (optional)')
    parser.add_argument('--seniority', default=None,
                       help='Preferred seniority level (optional)')
    parser.add_argument('--skip-extraction', action='store_true',
                       help='Skip job extraction after creating profile')
    
    args = parser.parse_args()
    
    # Get database connection string
    db_connection_string = os.getenv('DB_CONNECTION_STRING')
    if not db_connection_string:
        # Try to construct from individual env vars
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'postgres')
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', 'postgres')
        
        db_connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        logger.info(f"Using constructed connection string (host: {db_host})")
    
    try:
        # Create profile
        profile_id = create_profile(
            db_connection_string=db_connection_string,
            profile_name=args.profile_name,
            query=args.query,
            country=args.country,
            location=args.location,
            date_window=args.date_window,
            email=args.email,
            skills=args.skills,
            min_salary=args.min_salary,
            max_salary=args.max_salary,
            remote_preference=args.remote_preference,
            seniority=args.seniority
        )
        
        print(f"\n✓ Profile created successfully!")
        print(f"  Profile ID: {profile_id}")
        print(f"  Profile Name: {args.profile_name}")
        print(f"  Query: {args.query}")
        print(f"  Country: {args.country.upper()}")
        
        # Extract jobs if not skipped
        if not args.skip_extraction:
            print(f"\nExtracting jobs for profile {profile_id}...")
            
            extractor = JobExtractor(db_connection_string=db_connection_string)
            results = extractor.extract_all_jobs()
            
            if profile_id in results:
                job_count = results[profile_id]
                print(f"\n✓ Extraction complete!")
                print(f"  Jobs extracted: {job_count}")
                
                # Update profile with run statistics
                conn = psycopg2.connect(db_connection_string)
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE marts.profile_preferences
                            SET total_run_count = total_run_count + 1,
                                last_run_at = CURRENT_TIMESTAMP,
                                last_run_status = %s,
                                last_run_job_count = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE profile_id = %s
                        """, ('success' if job_count > 0 else 'no_jobs', job_count, profile_id))
                finally:
                    conn.close()
            else:
                print(f"\n⚠ No jobs extracted for profile {profile_id}")
        else:
            print(f"\n⚠ Job extraction skipped (use --skip-extraction=false to extract)")
        
        print(f"\n=== Summary ===")
        print(f"Profile ID: {profile_id}")
        print(f"Profile Name: {args.profile_name}")
        if not args.skip_extraction and profile_id in results:
            print(f"Jobs Extracted: {results[profile_id]}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Failed to create profile or extract jobs: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
