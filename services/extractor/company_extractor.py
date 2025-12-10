"""
Company Extractor Service

Extracts company data from Glassdoor API and writes to raw.glassdoor_companies table.
"""

import os
import logging
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Set
import psycopg2
from psycopg2.extras import execute_values
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
from rapidfuzz import fuzz

from .glassdoor_client import GlassdoorClient

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class CompanyExtractor:
    """
    Service for extracting company data from Glassdoor API.
    
    Scans staging.jsearch_job_postings for employer names, identifies companies
    not yet enriched, and calls Glassdoor API to fetch company data.
    """
    
    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        glassdoor_api_key: Optional[str] = None
    ):
        """
        Initialize the company extractor.
        
        Args:
            db_connection_string: PostgreSQL connection string. If None, reads from DB_CONNECTION_STRING env var.
            glassdoor_api_key: Glassdoor API key. If None, reads from GLASSDOOR_API_KEY env var.
        """
        self.db_connection_string = db_connection_string or os.getenv('DB_CONNECTION_STRING')
        self.glassdoor_api_key = glassdoor_api_key or os.getenv('GLASSDOOR_API_KEY')
        
        if not self.db_connection_string:
            raise ValueError("Database connection string is required (DB_CONNECTION_STRING env var)")
        if not self.glassdoor_api_key:
            raise ValueError("Glassdoor API key is required (GLASSDOOR_API_KEY env var)")
        
        self.client = GlassdoorClient(api_key=self.glassdoor_api_key)
    
    def get_companies_to_enrich(self, limit: Optional[int] = None) -> List[str]:
        """
        Get list of company lookup keys that need enrichment.
        
        Scans staging.jsearch_job_postings for unique employer names that are
        not yet in staging.glassdoor_companies or in the enrichment queue with success/not_found status.
        
        Args:
            limit: Maximum number of companies to return (None for all)
            
        Returns:
            List of company lookup keys (normalized company names)
        """
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                # Get unique employer names from staging that aren't already enriched
                # Check both staging.glassdoor_companies and company_enrichment_queue
                query = """
                    SELECT DISTINCT 
                        lower(trim(employer_name)) as company_lookup_key
                    FROM staging.jsearch_job_postings
                    WHERE employer_name IS NOT NULL 
                        AND trim(employer_name) != ''
                        AND lower(trim(employer_name)) NOT IN (
                            -- Exclude companies already in staging.glassdoor_companies
                            SELECT DISTINCT company_lookup_key 
                            FROM staging.glassdoor_companies
                            WHERE company_lookup_key IS NOT NULL
                        )
                        AND lower(trim(employer_name)) NOT IN (
                            -- Exclude companies already successfully enriched or marked as not_found
                            SELECT company_lookup_key 
                            FROM staging.company_enrichment_queue 
                            WHERE enrichment_status IN ('success', 'not_found')
                        )
                    ORDER BY company_lookup_key
                """
                
                if limit:
                    # Validate limit is a positive integer
                    if not isinstance(limit, int) or limit <= 0:
                        raise ValueError(f"Limit must be a positive integer, got: {limit}")
                    query += " LIMIT %s"
                    cur.execute(query, (limit,))
                else:
                    cur.execute(query)
                companies = [row[0] for row in cur.fetchall()]
                
                logger.info(f"Found {len(companies)} companies needing enrichment")
                return companies
                
        finally:
            conn.close()
    
    def mark_company_queued(self, company_lookup_key: str):
        """
        Mark a company as queued in the enrichment queue.
        
        Args:
            company_lookup_key: Normalized company name/domain
        """
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO staging.company_enrichment_queue (
                        company_lookup_key,
                        enrichment_status,
                        first_queued_at,
                        last_attempt_at,
                        attempt_count
                    ) VALUES (%s, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                    ON CONFLICT (company_lookup_key) 
                    DO UPDATE SET 
                        enrichment_status = 'pending',
                        last_attempt_at = CURRENT_TIMESTAMP,
                        attempt_count = staging.company_enrichment_queue.attempt_count + 1
                """, (company_lookup_key,))
                
        finally:
            conn.close()
    
    def extract_company(self, company_lookup_key: str) -> Optional[Dict[str, Any]]:
        """
        Extract company data from Glassdoor API for a single company.
        
        Uses fuzzy matching to select the best match when multiple results are returned.
        
        Args:
            company_lookup_key: Normalized company name/domain to search for
            
        Returns:
            Company data dictionary if found, None otherwise
        """
        logger.info(f"Searching Glassdoor for company: {company_lookup_key}")
        
        try:
            # Mark as queued
            self.mark_company_queued(company_lookup_key)
            
            # Call Glassdoor API 
            response = self.client.search_company(
                query=company_lookup_key,
                limit=10  # Get multiple results for fuzzy matching
            )
            
            # Check response
            if response.get('status') != 'OK':
                logger.warning(f"API returned non-OK status for {company_lookup_key}: {response.get('status')}")
                self._mark_company_error(company_lookup_key, f"API status: {response.get('status')}")
                return None
            
            companies_data = response.get('data', [])
            if not companies_data:
                logger.info(f"No company found for: {company_lookup_key}")
                self._mark_company_not_found(company_lookup_key)
                return None
            
            # Use fuzzy matching to select best match
            company_data = self._select_best_match(companies_data, company_lookup_key)
            
            if company_data:
                logger.info(f"Found company: {company_data.get('name', 'Unknown')} (ID: {company_data.get('company_id')})")
                return company_data
            else:
                logger.info(f"No company found with sufficient similarity for: {company_lookup_key}")
                self._mark_company_not_found(company_lookup_key)
                return None
            
        except Exception as e:
            logger.error(f"Error extracting company {company_lookup_key}: {e}", exc_info=True)
            self._mark_company_error(company_lookup_key, str(e))
            return None
    
    def _select_best_match(
        self, 
        companies_data: List[Dict[str, Any]], 
        company_lookup_key: str,
        similarity_threshold: float = 0.85
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best matching company from API results using fuzzy matching.
        
        Args:
            companies_data: List of company dictionaries from API
            company_lookup_key: Original normalized company name to match against
            similarity_threshold: Minimum similarity ratio (0.0-1.0) to accept a match. Default 0.85 (85%)
            
        Returns:
            Best matching company dictionary if similarity >= threshold, None otherwise
        """
        if not companies_data:
            return None
        
        if len(companies_data) == 1:
            # Only one result, return it if similarity is acceptable
            company_name = companies_data[0].get('name', '')
            similarity = fuzz.ratio(company_lookup_key.lower(), company_name.lower()) / 100.0
            if similarity >= similarity_threshold:
                return companies_data[0]
            else:
                logger.warning(
                    f"Single result similarity ({similarity:.2%}) below threshold "
                    f"({similarity_threshold:.2%}) for {company_lookup_key}"
                )
                return None
        
        # Multiple results - find best match
        best_match = None
        best_similarity = 0.0
        
        for company in companies_data:
            company_name = company.get('name', '')
            if not company_name:
                continue
            
            # Calculate similarity ratio (0-100, convert to 0-1)
            similarity = fuzz.ratio(company_lookup_key.lower(), company_name.lower()) / 100.0
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = company
        
        # Check if best match meets threshold
        if best_match and best_similarity >= similarity_threshold:
            logger.info(
                f"Selected best match: '{best_match.get('name')}' "
                f"(similarity: {best_similarity:.2%}) for '{company_lookup_key}'"
            )
            return best_match
        else:
            logger.warning(
                f"Best match similarity ({best_similarity:.2%}) below threshold "
                f"({similarity_threshold:.2%}) for {company_lookup_key}"
            )
            return None
    
    def _write_company_to_db(self, company_data: Dict[str, Any], company_lookup_key: str):
        """
        Write company data to raw.glassdoor_companies table.
        
        Args:
            company_data: Company dictionary from API
            company_lookup_key: Lookup key used to find the company
        """
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                now = datetime.now()
                today = date.today()
                
                # Generate surrogate key
                import hashlib
                company_id = company_data.get('company_id', '')
                key_string = f"{company_id}|{company_lookup_key}"
                glassdoor_companies_key = int(hashlib.md5(key_string.encode()).hexdigest()[:15], 16)
                
                # Note: Duplicates will be handled by staging layer deduplication
                cur.execute("""
                    INSERT INTO raw.glassdoor_companies (
                        glassdoor_companies_key,
                        raw_payload,
                        company_lookup_key,
                        dwh_load_date,
                        dwh_load_timestamp,
                        dwh_source_system
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    glassdoor_companies_key,
                    json.dumps(company_data),
                    company_lookup_key,
                    today,
                    now,
                    'glassdoor'
                ))
                
                # Mark as successful in enrichment queue
                self._mark_company_success(company_lookup_key)
                
        finally:
            conn.close()
    
    def _mark_company_success(self, company_lookup_key: str):
        """Mark company as successfully enriched."""
        self._update_enrichment_status(company_lookup_key, 'success')
    
    def _mark_company_not_found(self, company_lookup_key: str):
        """Mark company as not found."""
        self._update_enrichment_status(company_lookup_key, 'not_found')
    
    def _mark_company_error(self, company_lookup_key: str, error_message: str):
        """Mark company enrichment as error."""
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE staging.company_enrichment_queue
                    SET enrichment_status = 'error',
                        last_attempt_at = CURRENT_TIMESTAMP,
                        error_message = %s
                    WHERE company_lookup_key = %s
                """, (error_message[:500], company_lookup_key))
        finally:
            conn.close()
    
    def _update_enrichment_status(self, company_lookup_key: str, status: str):
        """Update enrichment status in queue."""
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE staging.company_enrichment_queue
                    SET enrichment_status = %s,
                        last_attempt_at = CURRENT_TIMESTAMP,
                        completed_at = CASE WHEN %s IN ('success', 'not_found') THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE company_lookup_key = %s
                """, (status, status, company_lookup_key))
        finally:
            conn.close()
    
    def extract_all_companies(self, limit: Optional[int] = None) -> Dict[str, str]:
        """
        Extract company data for all companies needing enrichment.
        
        Args:
            limit: Maximum number of companies to process (None for all)
            
        Returns:
            Dictionary mapping company_lookup_key to status (success/not_found/error)
        """
        companies = self.get_companies_to_enrich(limit=limit)
        
        if not companies:
            logger.info("No companies need enrichment")
            return {}
        
        results = {}
        for company_lookup_key in companies:
            try:
                company_data = self.extract_company(company_lookup_key)
                if company_data:
                    self._write_company_to_db(company_data, company_lookup_key)
                    results[company_lookup_key] = 'success'
                else:
                    results[company_lookup_key] = 'not_found'
            except Exception as e:
                logger.error(f"Failed to extract company {company_lookup_key}: {e}")
                results[company_lookup_key] = 'error'
        
        # Print summary
        success_count = sum(1 for v in results.values() if v == 'success')
        not_found_count = sum(1 for v in results.values() if v == 'not_found')
        error_count = sum(1 for v in results.values() if v == 'error')
        
        logger.info(f"Extraction complete. Success: {success_count}, Not Found: {not_found_count}, Errors: {error_count}")
        
        return results


def main():
    """Main entry point for running the company extractor as a standalone script."""
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        extractor = CompanyExtractor()
        results = extractor.extract_all_companies()
        
        # Print summary
        print("\n=== Extraction Summary ===")
        for company, status in results.items():
            print(f"{company}: {status}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
