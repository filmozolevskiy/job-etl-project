"""
Job Ranker Service

Ranks jobs based on profile preferences and writes scores to marts.dim_ranking.
"""

import os
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import re

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class JobRanker:
    """
    Service for ranking jobs based on profile preferences.
    
    Reads jobs from marts.fact_jobs and profiles from marts.profile_preferences,
    scores each job/profile pair, and writes rankings to marts.dim_ranking.
    """
    
    def __init__(self, db_connection_string: Optional[str] = None):
        """
        Initialize the job ranker.
        
        Args:
            db_connection_string: PostgreSQL connection string. If None, reads from DB_CONNECTION_STRING env var.
        """
        self.db_connection_string = db_connection_string or os.getenv('DB_CONNECTION_STRING')
        
        if not self.db_connection_string:
            raise ValueError("Database connection string is required (DB_CONNECTION_STRING env var)")
    
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
                        skills,
                        min_salary,
                        max_salary,
                        remote_preference,
                        seniority
                    FROM marts.profile_preferences
                    WHERE is_active = true
                    ORDER BY profile_id
                """)
                
                columns = [desc[0] for desc in cur.description]
                profiles = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                logger.info(f"Found {len(profiles)} active profile(s) for ranking")
                return profiles
                
        finally:
            conn.close()
    
    def get_jobs_for_profile(self, profile_id: int) -> List[Dict[str, Any]]:
        """
        Get jobs that were extracted for a specific profile.
        
        Args:
            profile_id: Profile ID to get jobs for
            
        Returns:
            List of job dictionaries from fact_jobs
        """
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                # Get jobs that were extracted for this profile
                # We join with raw.jsearch_job_postings to filter by profile_id
                cur.execute("""
                    SELECT DISTINCT
                        fj.jsearch_job_id,
                        fj.job_title,
                        fj.job_location,
                        fj.job_employment_type,
                        fj.job_is_remote,
                        fj.job_posted_at_datetime_utc,
                        fj.company_key
                    FROM marts.fact_jobs fj
                    INNER JOIN raw.jsearch_job_postings rjp
                        ON fj.jsearch_job_id = rjp.raw_payload->>'job_id'
                    WHERE rjp.profile_id = %s
                    ORDER BY fj.job_posted_at_datetime_utc DESC NULLS LAST
                """, (profile_id,))
                
                columns = [desc[0] for desc in cur.description]
                jobs = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                logger.debug(f"Found {len(jobs)} jobs for profile {profile_id}")
                return jobs
                
        finally:
            conn.close()
    
    def calculate_job_score(
        self,
        job: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> float:
        """
        Calculate match score for a single job against a profile.
        
        This is a pure calculation function that computes how well a job matches a profile.
        It does NOT write to database or modify any state - it only returns a score.
        
        Scoring factors (0-100 scale):
        - Location match: 0-40 points
        - Keyword match (query vs title): 0-40 points
        - Recency (newer = higher): 0-20 points
        
        Args:
            job: Job dictionary from fact_jobs
            profile: Profile dictionary from profile_preferences
            
        Returns:
            Match score from 0-100 (higher = better match)
        """
        score = 0.0
        
        # Factor 1: Location match (0-40 points)
        location_score = self._score_location_match(job, profile)
        score += location_score * 40.0
        
        # Factor 2: Keyword match (0-40 points)
        keyword_score = self._score_keyword_match(job, profile)
        score += keyword_score * 40.0
        
        # Factor 3: Recency (0-20 points)
        recency_score = self._score_recency(job)
        score += recency_score * 20.0
        
        # Ensure score is between 0 and 100
        return max(0.0, min(100.0, score))
    
    def _score_location_match(
        self,
        job: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> float:
        """
        Score location match between job and profile (0-1 scale).
        
        Args:
            job: Job dictionary
            profile: Profile dictionary
            
        Returns:
            Location match score (0.0-1.0)
        """
        job_location = (job.get('job_location') or '').lower()
        profile_location = (profile.get('location') or '').lower()
        profile_country = (profile.get('country') or '').lower()
        
        if not job_location:
            return 0.0
        
        # Exact location match
        if profile_location and profile_location in job_location:
            return 1.0
        
        # Country match
        if profile_country:
            # Common country name mappings
            country_mappings = {
                'ca': ['canada', 'canadian'],
                'us': ['united states', 'usa', 'u.s.', 'america'],
                'uk': ['united kingdom', 'england', 'britain'],
            }
            
            country_terms = country_mappings.get(profile_country, [profile_country])
            for term in country_terms:
                if term in job_location:
                    return 0.7  # Partial match for country
        
        return 0.0
    
    def _score_keyword_match(
        self,
        job: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> float:
        """
        Score keyword match between profile query and job title (0-1 scale).
        
        Args:
            job: Job dictionary
            profile: Profile dictionary
            
        Returns:
            Keyword match score (0.0-1.0)
        """
        job_title = (job.get('job_title') or '').lower()
        profile_query = (profile.get('query') or '').lower()
        
        if not profile_query or not job_title:
            return 0.0
        
        # Extract keywords from profile query
        query_keywords = set(re.findall(r'\b\w+\b', profile_query))
        
        if not query_keywords:
            return 0.0
        
        # Count matching keywords
        job_words = set(re.findall(r'\b\w+\b', job_title))
        matching_keywords = query_keywords.intersection(job_words)
        
        if not matching_keywords:
            return 0.0
        
        # Score based on percentage of keywords matched
        match_ratio = len(matching_keywords) / len(query_keywords)
        
        # Boost score if all keywords match
        if match_ratio == 1.0:
            return 1.0
        
        # Partial match score
        return match_ratio * 0.8  # Cap partial matches at 80%
    
    def _score_recency(self, job: Dict[str, Any]) -> float:
        """
        Score job recency (newer = higher score, 0-1 scale).
        
        Args:
            job: Job dictionary
            
        Returns:
            Recency score (0.0-1.0)
        """
        posted_at = job.get('job_posted_at_datetime_utc')
        
        if not posted_at:
            return 0.5  # Neutral score if date unknown
        
        # Calculate days since posting
        if isinstance(posted_at, str):
            try:
                posted_at = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            except:
                return 0.5
        
        now = datetime.now(posted_at.tzinfo) if posted_at.tzinfo else datetime.now()
        days_old = (now - posted_at).days
        
        # Score based on age:
        # 0 days = 1.0
        # 7 days = 0.7
        # 30 days = 0.3
        # 90+ days = 0.0
        
        if days_old < 0:
            return 1.0  # Future date (shouldn't happen, but handle gracefully)
        elif days_old == 0:
            return 1.0
        elif days_old <= 7:
            return 1.0 - (days_old * 0.04)  # Linear decay: 0.96, 0.92, ..., 0.72
        elif days_old <= 30:
            return 0.72 - ((days_old - 7) * 0.018)  # Continue decay to 0.3
        elif days_old <= 90:
            return 0.3 - ((days_old - 30) * 0.005)  # Slow decay to 0.0
        else:
            return 0.0
    
    def rank_jobs_for_profile(
        self,
        profile: Dict[str, Any]
    ) -> int:
        """
        Process and save rankings for all jobs belonging to a profile (workflow method).
        
        This method orchestrates the full ranking workflow:
        1. Retrieves all jobs extracted for this profile
        2. Calculates match scores for each job using calculate_job_score()
        3. Writes all rankings to marts.dim_ranking table
        
        This is the main entry point for ranking jobs - it handles the complete process
        from fetching jobs to persisting rankings in the database.
        
        Args:
            profile: Profile dictionary from profile_preferences
            
        Returns:
            Number of jobs ranked and saved to database
        """
        profile_id = profile['profile_id']
        profile_name = profile['profile_name']
        
        logger.info(f"Ranking jobs for profile {profile_id} ({profile_name})")
        
        # Get jobs for this profile
        jobs = self.get_jobs_for_profile(profile_id)
        
        if not jobs:
            logger.info(f"No jobs found for profile {profile_id}")
            return 0
        
        # Calculate scores for each job
        rankings = []
        now = datetime.now()
        today = date.today()
        
        for job in jobs:
            score = self.calculate_job_score(job, profile)
            rankings.append({
                'jsearch_job_id': job['jsearch_job_id'],
                'profile_id': profile_id,
                'rank_score': round(score, 2),
                'ranked_at': now,
                'ranked_date': today,
                'dwh_load_timestamp': now,
                'dwh_source_system': 'ranker'
            })
        
        # Write to database
        self._write_rankings(rankings)
        
        logger.info(f"Ranked {len(rankings)} jobs for profile {profile_id} (avg score: {sum(r['rank_score'] for r in rankings) / len(rankings):.2f})")
        
        return len(rankings)
    
    def _write_rankings(self, rankings: List[Dict[str, Any]]):
        """
        Write rankings to marts.dim_ranking table.
        Uses INSERT ... ON CONFLICT to update existing rankings.
        
        Args:
            rankings: List of ranking dictionaries
        """
        if not rankings:
            return
        
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                # Prepare data for bulk insert
                rows = []
                for ranking in rankings:
                    rows.append((
                        ranking['jsearch_job_id'],
                        ranking['profile_id'],
                        ranking['rank_score'],
                        ranking['ranked_at'],
                        ranking['ranked_date'],
                        ranking['dwh_load_timestamp'],
                        ranking['dwh_source_system']
                    ))
                
                # Bulk insert/update using execute_values
                execute_values(
                    cur,
                    """
                    INSERT INTO marts.dim_ranking (
                        jsearch_job_id,
                        profile_id,
                        rank_score,
                        ranked_at,
                        ranked_date,
                        dwh_load_timestamp,
                        dwh_source_system
                    ) VALUES %s
                    ON CONFLICT (jsearch_job_id, profile_id)
                    DO UPDATE SET
                        rank_score = EXCLUDED.rank_score,
                        ranked_at = EXCLUDED.ranked_at,
                        ranked_date = EXCLUDED.ranked_date,
                        dwh_load_timestamp = EXCLUDED.dwh_load_timestamp,
                        dwh_source_system = EXCLUDED.dwh_source_system
                    """,
                    rows
                )
                
        finally:
            conn.close()
    
    def rank_all_jobs(self) -> Dict[int, int]:
        """
        Rank jobs for all active profiles.
        
        Returns:
            Dictionary mapping profile_id to number of jobs ranked
        """
        profiles = self.get_active_profiles()
        
        if not profiles:
            logger.warning("No active profiles found for ranking")
            return {}
        
        results = {}
        for profile in profiles:
            try:
                count = self.rank_jobs_for_profile(profile)
                results[profile['profile_id']] = count
            except Exception as e:
                logger.error(f"Failed to rank jobs for profile {profile['profile_id']}: {e}", exc_info=True)
                results[profile['profile_id']] = 0
        
        total_ranked = sum(results.values())
        logger.info(f"Ranking complete. Total jobs ranked: {total_ranked}")
        
        return results


def main():
    """Main entry point for running the ranker as a standalone script."""
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        ranker = JobRanker()
        results = ranker.rank_all_jobs()
        
        # Print summary
        print("\n=== Ranking Summary ===")
        for profile_id, count in results.items():
            print(f"Profile {profile_id}: {count} jobs ranked")
        print(f"Total: {sum(results.values())} jobs ranked")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Ranking failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

