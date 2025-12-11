"""
Job Extractor Service

Extracts job postings from JSearch API and writes to raw.jsearch_job_postings table.
"""

import os
import logging
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

from .jsearch_client import JSearchClient

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class JobExtractor:
    """
    Service for extracting job postings from JSearch API.
    
    Reads active profiles from marts.profile_preferences, calls JSearch API
    for each profile, and writes raw JSON responses to raw.jsearch_job_postings.
    """
    
    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        jsearch_api_key: Optional[str] = None,
        num_pages: Optional[int] = None
    ):
        """
        Initialize the job extractor.
        
        Args:
            db_connection_string: PostgreSQL connection string. If None, reads from DB_CONNECTION_STRING env var.
            jsearch_api_key: JSearch API key. If None, reads from JSEARCH_API_KEY env var.
            num_pages: Number of pages to fetch per profile. If None, reads from JSEARCH_NUM_PAGES env var (default: 5).
        """
        self.db_connection_string = db_connection_string or os.getenv('DB_CONNECTION_STRING')
        self.jsearch_api_key = jsearch_api_key or os.getenv('JSEARCH_API_KEY')
        
        if not self.db_connection_string:
            raise ValueError("Database connection string is required (DB_CONNECTION_STRING env var)")
        if not self.jsearch_api_key:
            raise ValueError("JSearch API key is required (JSEARCH_API_KEY env var)")
        
        # Get num_pages from parameter, env var, or default to 5
        if num_pages is not None:
            self.num_pages = num_pages
        else:
            env_num_pages = os.getenv('JSEARCH_NUM_PAGES')
            self.num_pages = int(env_num_pages) if env_num_pages else 5
        
        self.client = JSearchClient(api_key=self.jsearch_api_key)
    
    def get_active_profiles(self) -> List[Dict[str, Any]]:
        """
        Get all active profiles from marts.profile_preferences.
        
        Returns:
            List of active profile dictionaries
        """
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        profile_id,
                        profile_name,
                        query,
                        location,
                        country,
                        date_window,
                        email
                    FROM marts.profile_preferences
                    WHERE is_active = true
                    ORDER BY profile_id
                """)
                
                columns = [desc[0] for desc in cur.description]
                profiles = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                logger.info(f"Found {len(profiles)} active profile(s)")
                return profiles
                
        finally:
            conn.close()
    
    def extract_jobs_for_profile(self, profile: Dict[str, Any]) -> int:
        """
        Extract jobs for a single profile and write to database.
        
        Args:
            profile: Profile dictionary with search parameters
            
        Returns:
            Number of jobs extracted
        """
        profile_id = profile['profile_id']
        profile_name = profile['profile_name']
        query = profile['query']
        
        logger.info(f"Extracting jobs for profile {profile_id} ({profile_name}): query='{query}'")
        
        try:
            # Call JSearch API
            response = self.client.search_jobs(
                query=query,
                location=profile.get('location'),
                country=profile.get('country'),
                date_posted=profile.get('date_window'),
                num_pages=self.num_pages
            )
            
            # Extract job data from response
            if response.get('status') != 'OK':
                logger.warning(f"API returned non-OK status: {response.get('status')}")
                return 0
            
            jobs_data = response.get('data', [])
            if not jobs_data:
                logger.info(f"No jobs found for profile {profile_id}")
                return 0
            
            # Write to database
            jobs_written = self._write_jobs_to_db(jobs_data, profile_id)
            logger.info(f"Extracted {jobs_written} jobs for profile {profile_id}")
            
            return jobs_written
            
        except Exception as e:
            logger.error(f"Error extracting jobs for profile {profile_id}: {e}", exc_info=True)
            raise
    
    def _write_jobs_to_db(self, jobs_data: List[Dict[str, Any]], profile_id: int) -> int:
        """
        Write job postings to raw.jsearch_job_postings table.
        
        Args:
            jobs_data: List of job posting dictionaries from API
            profile_id: Profile ID that triggered this extraction
            
        Returns:
            Number of jobs written
        """
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                now = datetime.now()
                today = date.today()
                
                # Prepare data for bulk insert
                rows = []
                for job in jobs_data:
                    # Generate surrogate key (using hash of job_id and profile_id for uniqueness)
                    import hashlib
                    job_id = job.get('job_id', '')
                    key_string = f"{job_id}|{profile_id}"
                    jsearch_job_postings_key = int(hashlib.md5(key_string.encode()).hexdigest()[:15], 16)
                    
                    rows.append((
                        jsearch_job_postings_key,
                        json.dumps(job),  # Store entire job object as JSONB
                        today,
                        now,
                        'jsearch',
                        profile_id
                    ))
                
                # Bulk insert using execute_values for efficiency
                # Note: Duplicates will be handled by staging layer deduplication
                execute_values(
                    cur,
                    """
                    INSERT INTO raw.jsearch_job_postings (
                        jsearch_job_postings_key,
                        raw_payload,
                        dwh_load_date,
                        dwh_load_timestamp,
                        dwh_source_system,
                        profile_id
                    ) VALUES %s
                    """,
                    rows
                )
                
                return len(rows)
                
        finally:
            conn.close()
    
    def extract_all_jobs(self) -> Dict[int, int]:
        """
        Extract jobs for all active profiles.
        
        Returns:
            Dictionary mapping profile_id to number of jobs extracted
        """
        profiles = self.get_active_profiles()
        
        if not profiles:
            logger.warning("No active profiles found. Please create at least one profile via the Profile Management UI.")
            return {}
        
        results = {}
        for profile in profiles:
            try:
                count = self.extract_jobs_for_profile(profile)
                results[profile['profile_id']] = count
            except Exception as e:
                logger.error(f"Failed to extract jobs for profile {profile['profile_id']}: {e}")
                results[profile['profile_id']] = 0
        
        total_jobs = sum(results.values())
        logger.info(f"Extraction complete. Total jobs extracted: {total_jobs}")
        
        return results


def main():
    """Main entry point for running the job extractor as a standalone script."""
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        extractor = JobExtractor()
        results = extractor.extract_all_jobs()
        
        # Print summary
        print("\n=== Extraction Summary ===")
        for profile_id, count in results.items():
            print(f"Profile {profile_id}: {count} jobs")
        print(f"Total: {sum(results.values())} jobs")
        
        sys.exit(0 if all(count > 0 for count in results.values()) else 1)
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
